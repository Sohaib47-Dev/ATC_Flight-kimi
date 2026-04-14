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
    #: Client lat/lon lerp segment length (seconds); lower = snappier marker toward each server snapshot.
    RADAR_INTERP_SEGMENT_SEC = float(os.environ.get("RADAR_INTERP_SEGMENT_SEC", "0.12"))
    _demo = os.environ.get("RADAR_DEMO_MODE", "").lower()
    RADAR_DEMO_MODE = _demo in ("1", "true", "yes", "on")
    RADAR_DEMO_ANIMATION_SPEED = float(os.environ.get("RADAR_DEMO_ANIMATION_SPEED", "3.0"))
    #: Multiplies along-route advance per sim tick (demo / presentation; not filed speed).
    try:
        _vis = float(os.environ.get("RADAR_SIM_VISUAL_MULTIPLIER", "3.0"))
    except ValueError:
        _vis = 1.0
    RADAR_SIM_VISUAL_MULTIPLIER = max(0.0, min(_vis, 50.0))
    #: Auto-create ``RTST*`` tracks for every FIR entry (defense radar stress test).
    RADAR_TEST_AUTO_SEED = os.environ.get("RADAR_TEST_AUTO_SEED", "").lower() in ("1", "true", "yes", "on")
    #: After each sim tick, validate routes/motion and log structured errors.
    RADAR_TEST_MONITOR = os.environ.get("RADAR_TEST_MONITOR", "").lower() in ("1", "true", "yes", "on")
    try:
        RADAR_TEST_CORRIDOR_NM = float(os.environ.get("RADAR_TEST_CORRIDOR_NM", "12"))
    except ValueError:
        RADAR_TEST_CORRIDOR_NM = 12.0
    try:
        RADAR_TEST_STUCK_TICKS = int(os.environ.get("RADAR_TEST_STUCK_TICKS", "12"))
    except ValueError:
        RADAR_TEST_STUCK_TICKS = 12


class DevelopmentConfig(Config):
    DEBUG = True
    #: Local stress-test defaults (override with env ``RADAR_TEST_*``).
    RADAR_TEST_AUTO_SEED = os.environ.get("RADAR_TEST_AUTO_SEED", "true").lower() in ("1", "true", "yes", "on")
    RADAR_TEST_MONITOR = os.environ.get("RADAR_TEST_MONITOR", "true").lower() in ("1", "true", "yes", "on")


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RADAR_SIM_USE_ETO = False
    RADAR_SIM_ETO_BYPASS = True
    #: Unit tests assert nominal NM advance; keep strict 1.0 while prod defaults may boost visibility.
    RADAR_SIM_VISUAL_MULTIPLIER = 1.0
    RADAR_TEST_AUTO_SEED = False
    RADAR_TEST_MONITOR = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
