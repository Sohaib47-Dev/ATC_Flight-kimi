"""Defense dashboard, radar, APIs, and message decryption."""
from datetime import datetime

from app.extensions import db
from app.models import DefenseMessage, TrackData
from modules.encryption import decrypt_track_data
from modules.flight_plan_parser import get_pakistan_fir_entries


def get_defense_dashboard_context():
    messages = DefenseMessage.query.filter_by(processed=False).order_by(
        DefenseMessage.received_at.desc()
    ).all()

    active_tracks = TrackData.query.filter_by(
        sent_to_defense=True,
        status='active'
    ).all()

    return {'messages': messages, 'active_tracks': active_tracks}


def get_radar_context():
    active_tracks = TrackData.query.filter_by(
        sent_to_defense=True,
        status='active'
    ).all()
    fir_entries = get_pakistan_fir_entries()
    return {'active_tracks': active_tracks, 'fir_entries': fir_entries}


def list_active_defense_tracks():
    return TrackData.query.filter_by(
        sent_to_defense=True,
        status='active'
    ).all()


def build_new_alerts_payload():
    new_messages = DefenseMessage.query.filter_by(processed=False).order_by(
        DefenseMessage.received_at.desc()
    ).all()

    alerts = []
    for msg in new_messages:
        track = msg.track_data
        alerts.append({
            'id': msg.id,
            'callsign': track.callsign,
            'fir_entry': track.fir_entry,
            'aircraft_type': track.aircraft_type,
            'cfl': track.cfl,
            'ssr': track.ssr,
            'received_at': msg.received_at.isoformat()
        })
    return alerts


def decrypt_message_and_mark_processed(message):
    """
    Decrypt defense message body and mark processed. Returns decrypted_data.
    Commits on success. Caller handles exceptions for flash/redirect.
    """
    decrypted_data = decrypt_track_data(message.encrypted_data)
    message.decrypted_at = datetime.utcnow()
    message.processed = True
    db.session.commit()
    return decrypted_data
