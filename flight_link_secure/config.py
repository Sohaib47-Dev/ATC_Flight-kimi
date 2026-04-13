"""
Application configuration — environment-driven; defaults centralized here.
"""
import os


class Config:
    """Base settings shared by all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "flight-link-secure-dev-key-2024")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///flight_link.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    #: When True, tracks do not advance until ``eto_utc`` (HHMM UTC today).
    RADAR_SIM_USE_ETO = os.environ.get("RADAR_SIM_USE_ETO", "").lower() in ("1", "true", "yes", "on")
    #: When True, ignore ETO gate (default so existing behavior matches pre-ETO sim).
    _eto_bypass = os.environ.get("RADAR_SIM_ETO_BYPASS", "true").lower()
    RADAR_SIM_ETO_BYPASS = _eto_bypass in ("1", "true", "yes", "on")
    #: How often the defense radar page calls ``GET /api/defense/tracks`` (ms). Lower = smoother
    #: server-side motion on the map (each poll advances sim by wall ``dt``). Env: ``RADAR_UI_POLL_MS``.
    _radar_ui_poll_ms = int(os.environ.get("RADAR_UI_POLL_MS", "500"))
    RADAR_UI_POLL_MS = _radar_ui_poll_ms
    #: Server WebSocket broadcast interval (ms); each tick advances simulation once for all clients.
    RADAR_WS_TICK_MS = int(os.environ.get("RADAR_WS_TICK_MS", str(_radar_ui_poll_ms)))
    #: Client lat/lon lerp segment length (seconds) — align with ~RADAR_WS_TICK_MS for smooth motion.
    RADAR_INTERP_SEGMENT_SEC = float(os.environ.get("RADAR_INTERP_SEGMENT_SEC", "0.45"))
    _demo = os.environ.get("RADAR_DEMO_MODE", "").lower()
    RADAR_DEMO_MODE = _demo in ("1", "true", "yes", "on")
    RADAR_DEMO_ANIMATION_SPEED = float(os.environ.get("RADAR_DEMO_ANIMATION_SPEED", "3.0"))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RADAR_SIM_USE_ETO = False
    RADAR_SIM_ETO_BYPASS = True


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
