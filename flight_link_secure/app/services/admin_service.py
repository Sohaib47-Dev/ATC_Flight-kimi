"""Admin dashboard, users, data integrity, and maintenance actions."""
from app.extensions import db
from app.models import User, FlightPlan, TrackData, SystemLog, DefenseMessage
from modules.flight_plan_parser import FlightPlanParser


def get_admin_dashboard_payload():
    """Statistics and recent activity for admin dashboard template."""
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'inactive_users': User.query.filter_by(is_active=False).count(),
        'total_flight_plans': FlightPlan.query.count(),
        'total_tracks': TrackData.query.count(),
        'active_tracks': TrackData.query.filter_by(status='active').count(),
        'completed_tracks': TrackData.query.filter_by(status='completed').count(),
        'terminated_tracks': TrackData.query.filter_by(status='terminated').count(),
        'sent_to_defense': TrackData.query.filter_by(sent_to_defense=True).count(),
        'pending_transfer': TrackData.query.filter_by(status='active', sent_to_defense=False).count(),
        'defense_messages': DefenseMessage.query.count(),
        'processed_messages': DefenseMessage.query.filter_by(processed=True).count(),
        'unprocessed_messages': DefenseMessage.query.filter_by(processed=False).count()
    }

    recent_logs = SystemLog.query.order_by(SystemLog.timestamp.desc()).limit(10).all()
    recent_submissions = SystemLog.query.filter(
        SystemLog.action.in_(['FLIGHT_PLAN_ADDED', 'FLIGHT_PLAN_REPLACED'])
    ).order_by(SystemLog.timestamp.desc()).limit(5).all()
    recent_transfers = SystemLog.query.filter_by(
        action='DATA_TRANSFERRED'
    ).order_by(SystemLog.timestamp.desc()).limit(5).all()

    online_users = User.query.filter(
        User.last_login_time.isnot(None)
    ).order_by(User.last_login_time.desc()).limit(10).all()

    duplicate_callsigns = db.session.query(
        FlightPlan.callsign,
        db.func.count(FlightPlan.id).label('count')
    ).group_by(FlightPlan.callsign).having(db.func.count(FlightPlan.id) > 1).all()

    stats['duplicate_flight_plans'] = len(duplicate_callsigns)

    return {
        'stats': stats,
        'recent_logs': recent_logs,
        'recent_submissions': recent_submissions,
        'recent_transfers': recent_transfers,
        'online_users': online_users,
    }


def toggle_user_active(user, is_active):
    """Set user active flag; caller commits and logs."""
    user.is_active = is_active
    db.session.commit()


def reset_user_password(user, new_password):
    """Set password; caller commits and logs."""
    user.set_password(new_password)
    db.session.commit()


def update_user_role_and_status(user, role, is_active):
    """Update role and status; caller commits and logs."""
    user.role = role
    user.is_active = is_active
    db.session.commit()


def get_data_integrity_context():
    """Build data integrity page context."""
    duplicate_callsigns = db.session.query(
        FlightPlan.callsign,
        db.func.count(FlightPlan.id).label('count')
    ).group_by(FlightPlan.callsign).having(db.func.count(FlightPlan.id) > 1).all()

    duplicate_plans = []
    for callsign, count in duplicate_callsigns:
        plans = FlightPlan.query.filter_by(callsign=callsign).all()
        duplicate_plans.append({
            'callsign': callsign,
            'count': count,
            'plans': plans
        })

    ssr_conflicts = db.session.query(
        TrackData.ssr,
        db.func.count(TrackData.id).label('count')
    ).filter(
        TrackData.status == 'active'
    ).group_by(TrackData.ssr).having(db.func.count(TrackData.id) > 1).all()

    ssr_conflict_tracks = []
    for ssr, count in ssr_conflicts:
        tracks = TrackData.query.filter_by(ssr=ssr, status='active').all()
        ssr_conflict_tracks.append({
            'ssr': ssr,
            'count': count,
            'tracks': tracks
        })

    orphaned_tracks = TrackData.query.filter(
        ~TrackData.flight_plan_id.in_(
            db.session.query(FlightPlan.id)
        )
    ).all()

    problematic_plans = []
    all_plans = FlightPlan.query.limit(50).all()
    for plan in all_plans:
        parser = FlightPlanParser()
        parsed = parser.parse(plan.raw_flight_plan)
        if not parsed or parser.get_errors():
            problematic_plans.append({
                'plan': plan,
                'errors': parser.get_errors() if parser.get_errors() else ['Unknown parsing error']
            })

    return {
        'duplicate_plans': duplicate_plans,
        'ssr_conflict_tracks': ssr_conflict_tracks,
        'orphaned_tracks': orphaned_tracks,
        'problematic_plans': problematic_plans,
    }


def admin_delete_flight_plan_if_safe(flight_plan):
    """
    Delete flight plan when no active tracks exist.
    Returns (success: bool, message: str, status_code: int or None).
    """
    plan_id = flight_plan.id
    active_tracks = TrackData.query.filter_by(
        flight_plan_id=plan_id,
        status='active'
    ).count()

    if active_tracks > 0:
        return False, f'Cannot delete: {active_tracks} active track(s) exist', 400

    db.session.delete(flight_plan)
    db.session.commit()
    return True, 'Flight plan deleted successfully', None
