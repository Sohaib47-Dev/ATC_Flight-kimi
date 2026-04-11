"""Admin panel routes."""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required

from app.models import User, FlightPlan, TrackData, SystemLog
from app.services import audit_service, admin_service
from app.utils.decorators import admin_required

bp = Blueprint('admin', __name__)


@bp.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    payload = admin_service.get_admin_dashboard_payload()
    return render_template(
        'admin/dashboard.html',
        stats=payload['stats'],
        recent_logs=payload['recent_logs'],
        recent_submissions=payload['recent_submissions'],
        recent_transfers=payload['recent_transfers'],
        online_users=payload['online_users'],
    )


@bp.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """View all users"""
    users = User.query.all()
    return render_template('admin/users.html', users=users)


@bp.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def admin_toggle_user_status(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    user.is_active = data.get('is_active', True)
    admin_service.toggle_user_active(user, user.is_active)

    action = 'ACTIVATED' if user.is_active else 'DEACTIVATED'
    audit_service.log_action(f'USER_{action}', f'User {user.username} (ID: {user_id})')

    return jsonify({'success': True, 'message': f'User {action.lower()} successfully'})


@bp.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def admin_reset_password(user_id):
    """Reset user password"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    new_password = data.get('new_password')
    if not new_password or len(new_password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

    admin_service.reset_user_password(user, new_password)

    audit_service.log_action('PASSWORD_RESET', f'Password reset for user {user.username} (ID: {user_id})')

    return jsonify({'success': True, 'message': 'Password reset successfully'})


@bp.route('/admin/users/<int:user_id>/update', methods=['POST'])
@login_required
@admin_required
def admin_update_user(user_id):
    """Update user role and status"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    old_role = user.role
    new_role = data.get('role', user.role)
    new_active = data.get('is_active', user.is_active)
    admin_service.update_user_role_and_status(user, new_role, new_active)

    audit_service.log_action(
        'USER_UPDATED',
        f'User {user.username} (ID: {user_id}) updated - Role: {old_role} -> {user.role}'
    )

    return jsonify({'success': True, 'message': 'User updated successfully'})


@bp.route('/admin/flight-plans')
@login_required
@admin_required
def admin_flight_plans():
    """View all flight plans"""
    flight_plans = FlightPlan.query.order_by(FlightPlan.created_at.desc()).all()
    return render_template('admin/flight_plans.html', flight_plans=flight_plans)


@bp.route('/admin/track-data')
@login_required
@admin_required
def admin_track_data():
    """View all track data"""
    tracks = TrackData.query.order_by(TrackData.created_at.desc()).all()
    return render_template('admin/track_data.html', tracks=tracks)


@bp.route('/admin/logs')
@login_required
@admin_required
def admin_logs():
    """View system logs"""
    logs = SystemLog.query.order_by(SystemLog.timestamp.desc()).limit(100).all()
    return render_template('admin/logs.html', logs=logs)


@bp.route('/admin/data-integrity')
@login_required
@admin_required
def admin_data_integrity():
    """Data integrity and validation checks"""
    ctx = admin_service.get_data_integrity_context()
    return render_template('admin/data_integrity.html', **ctx)


@bp.route('/admin/flight-plans/<int:plan_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_flight_plan(plan_id):
    """Delete a flight plan from admin panel"""
    flight_plan = FlightPlan.query.get_or_404(plan_id)
    callsign = flight_plan.callsign

    success, message, err_code = admin_service.admin_delete_flight_plan_if_safe(flight_plan)

    if not success:
        return jsonify({'success': False, 'message': message}), err_code

    audit_service.log_action(
        'ADMIN_FLIGHT_PLAN_DELETED',
        f'Admin deleted flight plan: {callsign} (ID: {plan_id})'
    )

    return jsonify({'success': True, 'message': message})
