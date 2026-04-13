"""
Flight-Link Secure application factory.
"""
import os

from flask import Flask, flash, redirect, url_for

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app(config_name=None):
    """
    Application factory. Configure with FLASK_CONFIG (development | production | testing)
    or pass config_name explicitly.
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'development')

    from config import config_by_name

    app = Flask(
        __name__,
        template_folder=os.path.join(_ROOT, 'templates'),
        static_folder=os.path.join(_ROOT, 'static'),
    )
    app.config.from_object(config_by_name[config_name])

    from app.extensions import db, login_manager, csrf, socketio

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app, cors_allowed_origins=None)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes import auth, admin, atc, defense

    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(atc.bp)
    app.register_blueprint(defense.bp)

    from app.socketio_handlers import register_radar_socketio

    register_radar_socketio(app, socketio)

    @app.errorhandler(403)
    def forbidden(error):
        flash('Access denied', 'error')
        return redirect(url_for('auth.index'))

    @app.errorhandler(404)
    def not_found(error):
        flash('Page not found', 'error')
        return redirect(url_for('auth.index'))

    return app
