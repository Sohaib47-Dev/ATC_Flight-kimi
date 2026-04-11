"""System audit logging."""
from flask import request
from flask_login import current_user

from app.extensions import db
from app.models import SystemLog


def log_action(action, details=None):
    """Log system action"""
    log = SystemLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        username=current_user.username if current_user.is_authenticated else 'Anonymous',
        action=action,
        details=details,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
