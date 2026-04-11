"""Defense operator routes and defense-facing APIs."""
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required

from app.models import DefenseMessage
from app.services import audit_service, defense_service
from app.utils.decorators import defense_required

bp = Blueprint('defense', __name__)


@bp.route('/defense/dashboard')
@login_required
@defense_required
def defense_dashboard():
    """Defense dashboard"""
    ctx = defense_service.get_defense_dashboard_context()
    return render_template(
        'defense/dashboard.html',
        messages=ctx['messages'],
        active_tracks=ctx['active_tracks'],
    )


@bp.route('/defense/radar')
@login_required
@defense_required
def defense_radar():
    """Defense radar simulator"""
    ctx = defense_service.get_radar_context()
    return render_template(
        'defense/radar.html',
        active_tracks=ctx['active_tracks'],
        fir_entries=ctx['fir_entries'],
    )


@bp.route('/api/defense/tracks')
@login_required
@defense_required
def api_defense_tracks():
    """API endpoint for radar track data"""
    tracks = defense_service.list_active_defense_tracks()
    return jsonify([track.to_dict() for track in tracks])


@bp.route('/api/defense/new-alerts')
@login_required
@defense_required
def api_defense_new_alerts():
    """API endpoint for new unprocessed alerts"""
    alerts = defense_service.build_new_alerts_payload()
    return jsonify(alerts)


@bp.route('/defense/message/<int:message_id>')
@login_required
@defense_required
def defense_message_detail(message_id):
    """View decrypted defense message"""
    message = DefenseMessage.query.get_or_404(message_id)

    try:
        decrypted_data = defense_service.decrypt_message_and_mark_processed(message)
        audit_service.log_action('MESSAGE_DECRYPTED', f'Message ID: {message_id}')

        return render_template(
            'defense/message_detail.html',
            message=message,
            decrypted_data=decrypted_data
        )
    except Exception as e:
        flash(f'Failed to decrypt message: {str(e)}', 'error')
        return redirect(url_for('defense.defense_dashboard'))
