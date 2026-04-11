"""Role-based access control decorators."""
from functools import wraps
from flask import abort
from flask_login import current_user


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def atc_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_atc() or current_user.is_admin()):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def defense_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_defense() or current_user.is_admin()):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
