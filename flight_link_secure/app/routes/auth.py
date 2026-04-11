"""Authentication: landing, login, logout."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models import User
from app.services import audit_service

bp = Blueprint('auth', __name__)


@bp.route('/')
def index():
    """Landing page"""
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('admin.admin_dashboard'))
        elif current_user.is_atc():
            return redirect(url_for('atc.atc_dashboard'))
        elif current_user.is_defense():
            return redirect(url_for('defense.defense_dashboard'))
    return render_template('index.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            user.last_login_ip = request.remote_addr
            user.last_login_time = datetime.utcnow()
            db.session.commit()

            login_user(user)
            audit_service.log_action('LOGIN', f'User {username} logged in from {request.remote_addr}')

            flash(f'Welcome, {username}!', 'success')

            if user.is_admin():
                return redirect(url_for('admin.admin_dashboard'))
            elif user.is_atc():
                return redirect(url_for('atc.atc_dashboard'))
            elif user.is_defense():
                return redirect(url_for('defense.defense_dashboard'))
        else:
            flash('Invalid username or password', 'error')
            audit_service.log_action(
                'LOGIN_FAILED',
                f'Failed login attempt for {username} from {request.remote_addr}'
            )

    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    """User logout"""
    audit_service.log_action('LOGOUT', f'User {current_user.username} logged out')
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.index'))
