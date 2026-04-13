"""Flask-SocketIO: defense radar real-time track broadcasts."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_broadcast_started = False


def register_radar_socketio(app: Flask, socketio: SocketIO) -> None:
    """Register connect handler and start a single global sim broadcast loop."""

    def radar_broadcast_loop() -> None:
        from app.services import simulation_service

        while True:
            try:
                with app.app_context():
                    ms = int(app.config.get("RADAR_WS_TICK_MS", 500))
                    rows = simulation_service.advance_defense_tracks_and_build_payload()
                    minimal = simulation_service.defense_tracks_minimal_ws_payload(rows)
                    socketio.emit("aircraft_update", {"tracks": minimal})
                socketio.sleep(max(0.05, float(ms) / 1000.0))
            except Exception:
                logger.exception("radar_broadcast_loop failed")
                socketio.sleep(1.0)

    @socketio.on("connect")
    def on_connect() -> bool:
        global _broadcast_started
        from flask_login import current_user

        if not current_user.is_authenticated:
            return False
        if not (current_user.is_defense() or current_user.is_admin()):
            return False
        if not app.config.get("TESTING") and not _broadcast_started:
            _broadcast_started = True
            socketio.start_background_task(radar_broadcast_loop)
        return True
