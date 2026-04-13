"""
Database models for Flight-Link Secure — schema unchanged from original models.py.
"""
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

from app.extensions import db


class User(db.Model):
    """User model for authentication and role management"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, atc, defense
    last_login_ip = db.Column(db.String(45), nullable=True)
    last_login_time = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        """Return user ID for Flask-Login session management"""
        return str(self.id)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def is_admin(self):
        return self.role == 'admin'

    def is_atc(self):
        return self.role == 'atc'

    def is_defense(self):
        return self.role == 'defense'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'last_login_ip': self.last_login_ip,
            'last_login_time': self.last_login_time.isoformat() if self.last_login_time else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }


class FlightPlan(db.Model):
    """Flight Plan model - stores raw ICAO flight plans"""
    __tablename__ = 'flight_plans'

    id = db.Column(db.Integer, primary_key=True)
    callsign = db.Column(db.String(20), unique=True, nullable=False, index=True)
    raw_flight_plan = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    track_data = db.relationship('TrackData', backref='flight_plan', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'callsign': self.callsign,
            'raw_flight_plan': self.raw_flight_plan,
            'created_at': self.created_at.isoformat()
        }


class TrackData(db.Model):
    """Track Data model - stores processed flight data with ATC estimates"""
    __tablename__ = 'track_data'

    id = db.Column(db.Integer, primary_key=True)

    flight_plan_id = db.Column(db.Integer, db.ForeignKey('flight_plans.id'), nullable=False)

    callsign = db.Column(db.String(20), nullable=False, index=True)
    aircraft_type = db.Column(db.String(10), nullable=False)
    departure = db.Column(db.String(4), nullable=False)
    destination = db.Column(db.String(4), nullable=False)
    fir_entry = db.Column(db.String(10), nullable=False)
    speed = db.Column(db.String(10), nullable=False)
    route = db.Column(db.Text, nullable=True)

    eto_utc = db.Column(db.String(4), nullable=False)
    eto_pst = db.Column(db.String(4), nullable=False)
    cfl = db.Column(db.String(3), nullable=False)
    ssr = db.Column(db.String(4), nullable=False)

    status = db.Column(db.String(20), default='active')
    sent_to_defense = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    #: Last server-side radar simulation integration time (UTC naive).
    last_simulated_at = db.Column(db.DateTime, nullable=True)

    #: JSON: server sim ``{lat, lon, along_nm, path_hash, x, y}`` (see simulation_service).
    current_position = db.Column(db.Text, nullable=True)

    def set_position(self, x, y):
        self.current_position = json.dumps({'x': x, 'y': y})

    def get_position(self):
        if self.current_position:
            return json.loads(self.current_position)
        return None

    @property
    def is_active(self):
        """True when this track is still active (shown on defense radar when transferred)."""
        return (self.status or '').lower() == 'active'

    def to_dict(self):
        return {
            'id': self.id,
            'callsign': self.callsign,
            'aircraft_type': self.aircraft_type,
            'departure': self.departure,
            'destination': self.destination,
            'fir_entry': self.fir_entry,
            'speed': self.speed,
            'route': self.route,
            'eto_utc': self.eto_utc,
            'eto_pst': self.eto_pst,
            'cfl': self.cfl,
            'ssr': self.ssr,
            'status': self.status,
            'is_active': self.is_active,
            'sent_to_defense': self.sent_to_defense,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'end_time': self.completed_at.isoformat() if self.completed_at else None,
            'position': self.get_position()
        }


class SystemLog(db.Model):
    """System Log model for monitoring and auditing"""
    __tablename__ = 'system_logs'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    username = db.Column(db.String(80), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'username': self.username,
            'action': self.action,
            'details': self.details,
            'ip_address': self.ip_address
        }


class DefenseMessage(db.Model):
    """Defense Message model - stores encrypted messages received from ATC"""
    __tablename__ = 'defense_messages'

    id = db.Column(db.Integer, primary_key=True)
    track_data_id = db.Column(db.Integer, db.ForeignKey('track_data.id', ondelete='CASCADE'), nullable=False)
    encrypted_data = db.Column(db.Text, nullable=False)
    received_at = db.Column(db.DateTime, default=datetime.utcnow)
    decrypted_at = db.Column(db.DateTime, nullable=True)
    processed = db.Column(db.Boolean, default=False)

    track_data = db.relationship('TrackData', backref=db.backref('defense_messages', cascade='all, delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id,
            'track_data_id': self.track_data_id,
            'received_at': self.received_at.isoformat(),
            'decrypted_at': self.decrypted_at.isoformat() if self.decrypted_at else None,
            'processed': self.processed
        }


def init_db(app):
    """Initialize the database with default admin user"""
    with app.app_context():
        db.create_all()
        from app.services.simulation_service import ensure_track_last_simulated_column

        ensure_track_last_simulated_column(app)

        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)

        atc = User.query.filter_by(username='atc').first()
        if not atc:
            atc = User(username='atc', role='atc')
            atc.set_password('atc123')
            db.session.add(atc)

        defense = User.query.filter_by(username='defense').first()
        if not defense:
            defense = User(username='defense', role='defense')
            defense.set_password('defense123')
            db.session.add(defense)

        db.session.commit()

        print("Database initialized with default users:")
        print("  Admin: admin / admin123")
        print("  ATC: atc / atc123")
        print("  Defense: defense / defense123")
