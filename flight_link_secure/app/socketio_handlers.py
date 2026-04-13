"""Flask-SocketIO: defense radar real-time track broadcasts."""
from __future__ import annotations

import logging

from flask import Flask
from flask_socketio import SocketIO

logger = logging.getLogger(__name__)

_broadcast_started = False


def register_radar_socketio(app: Flask, socketio: SocketIO) -> None:
    """Register connect handler and start a single global sim broadcast loop."""

    def radar_broadcast_loop() -> None:
        from app.services import radar_test_monitor
        from app.services import simulation_service

        while True:
            try:
                with app.app_context():
                    ms = int(app.config.get("RADAR_WS_TICK_MS", 500))
                    rows = simulation_service.advance_defense_tracks_and_build_payload(app)
                    minimal = simulation_service.defense_tracks_minimal_ws_payload(rows)
                    socketio.emit("aircraft_update", {"tracks": minimal})
                    stats = radar_test_monitor.get_last_stats()
                    tick = stats.get("tick")
                    fails = int(stats.get("failures") or 0)
                    emit_stats = False
                    if isinstance(tick, int) and tick > 0:
                        # Frequent updates early so the overlay does not sit on "waiting…";
                        # then throttle; always push when there are failures.
                        emit_stats = tick <= 10 or tick % 5 == 0 or fails > 0
                    if emit_stats and stats:
                        socketio.emit("radar_test_stats", stats)
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
            with app.app_context():
                from app.services import radar_test_seed

                radar_test_seed.try_auto_seed(app)
            socketio.start_background_task(radar_broadcast_loop)
        return True
