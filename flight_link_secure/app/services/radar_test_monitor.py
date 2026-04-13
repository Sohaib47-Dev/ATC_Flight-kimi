"""
Real-time validation of defense radar tracks (FIR entry, route path, motion, corridor).

Runs after each simulation tick when ``RADAR_TEST_MONITOR`` is enabled. Logs structured
errors and performs light DB autofixes (entry normalization, empty route fill-in).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from flask import Flask

from app.extensions import db
from app.models import TrackData
from app.services.kinematics import haversine_nm, latlon_to_svg_xy
from app.services.route_builder import (
    build_simulated_route_path,
    normalize_fir_entry_key,
    resolve_fir_entry_lat_lon,
)

logger = logging.getLogger(__name__)

_state: dict[int, dict[str, Any]] = {}
_last_stats: dict[str, Any] = {}
_stats_tick = 0

_DEFAULT_CORRIDOR_NM = 12.0
_DEFAULT_STUCK_TICKS = 12


def min_nm_to_resolved_path(lat: float, lon: float, resolved_path: list[dict]) -> float:
    """Minimum great-circle NM from (lat,lon) to the polyline (closest point per segment, SVG t)."""
    if not resolved_path or len(resolved_path) < 2:
        return 1e9
    try:
        px, py = latlon_to_svg_xy(lat, lon)
    except Exception:
        return 1e9
    best = 1e9
    for i in range(len(resolved_path) - 1):
        a = resolved_path[i]
        b = resolved_path[i + 1]
        la, lo = float(a.get("lat", 0)), float(a.get("lon", 0))
        lb, lo2 = float(b.get("lat", 0)), float(b.get("lon", 0))
        ax, ay = latlon_to_svg_xy(la, lo)
        bx, by = latlon_to_svg_xy(lb, lo2)
        abx, aby = bx - ax, by - ay
        apx, apy = px - ax, py - ay
        ab2 = abx * abx + aby * aby
        t = (apx * abx + apy * aby) / ab2 if ab2 > 1e-12 else 0.0
        t = max(0.0, min(1.0, t))
        glam = la + (lb - la) * t
        glom = lo + (lo2 - lo) * t
        d = haversine_nm(lat, lon, glam, glom)
        if d < best:
            best = d
    return best


def _log_error(
    *,
    error_type: str,
    aircraft_id: int | None,
    callsign: str,
    fir_entry: str,
    route: str,
    extra: dict | None = None,
) -> None:
    rec: dict[str, Any] = {
        "error_type": error_type,
        "aircraft_id": aircraft_id,
        "callsign": callsign,
        "fir_entry": fir_entry,
        "route": route,
    }
    if extra:
        rec.update(extra)
    logger.warning("RADAR_TEST_EVENT %s", json.dumps(rec, default=str))


def get_last_stats() -> dict[str, Any]:
    """Snapshot for WebSocket overlay (updated each monitor tick)."""
    return dict(_last_stats) if _last_stats else {}


def process_tick(app: Flask, rows: list[dict[str, Any]]) -> None:
    global _stats_tick, _last_stats
    if not app.config.get("RADAR_TEST_MONITOR"):
        _last_stats = {}
        return

    corridor = float(app.config.get("RADAR_TEST_CORRIDOR_NM", _DEFAULT_CORRIDOR_NM))
    stuck_ticks = int(app.config.get("RADAR_TEST_STUCK_TICKS", _DEFAULT_STUCK_TICKS))

    active = 0
    failures = 0
    completed = 0
    recent: list[dict[str, Any]] = []

    for row in rows:
        tid = int(row["id"])
        callsign = str(row.get("callsign", ""))
        fir_entry = str(row.get("fir_entry", "") or "")
        route = str(row.get("route") or "")
        status = str(row.get("status", "") or "").lower()
        sim_active = bool(row.get("sim_active", False))
        lat = row.get("lat")
        lon = row.get("lon")
        along = row.get("along_nm")
        path_total = float(row.get("path_total_nm") or 0.0)
        resolved = row.get("resolved_path") or []

        if status == "completed":
            completed += 1
            _state.pop(tid, None)
            continue

        if status != "active" or row.get("sent_to_defense") is False:
            continue

        active += 1
        track: TrackData | None = db.session.get(TrackData, tid)

        entry_ll = resolve_fir_entry_lat_lon(fir_entry)
        if entry_ll is None and track is not None:
            nk = normalize_fir_entry_key(track.fir_entry)
            if nk and nk != (track.fir_entry or "").strip().upper():
                track.fir_entry = nk
                db.session.add(track)
                entry_ll = resolve_fir_entry_lat_lon(track.fir_entry)
                if entry_ll:
                    _log_error(
                        error_type="ENTRY_AUTOFIX_NORMALIZED",
                        aircraft_id=tid,
                        callsign=callsign,
                        fir_entry=fir_entry,
                        route=route,
                        extra={"new_entry": track.fir_entry},
                    )

        if entry_ll is None:
            failures += 1
            _log_error(
                error_type="ENTRY_RESOLUTION_FAILED",
                aircraft_id=tid,
                callsign=callsign,
                fir_entry=fir_entry,
                route=route,
            )
            recent.append(
                {"type": "ENTRY_RESOLUTION_FAILED", "callsign": callsign, "id": tid}
            )
            continue

        if not isinstance(resolved, list) or len(resolved) < 2 or path_total <= 0.0:
            failures += 1
            _log_error(
                error_type="EMPTY_ROUTE_PATH",
                aircraft_id=tid,
                callsign=callsign,
                fir_entry=fir_entry,
                route=route,
                extra={"path_total_nm": path_total, "n_pts": len(resolved) if isinstance(resolved, list) else 0},
            )
            recent.append({"type": "EMPTY_ROUTE_PATH", "callsign": callsign, "id": tid})
            if track is not None and (not track.route or not str(track.route).strip()):
                fe = normalize_fir_entry_key(track.fir_entry) or track.fir_entry
                track.route = f"{fe} M875 M881 LAJAK".strip()
                db.session.add(track)
                _log_error(
                    error_type="ROUTE_AUTOFIX_DEFAULT",
                    aircraft_id=tid,
                    callsign=callsign,
                    fir_entry=fir_entry,
                    route=track.route,
                )
            continue

        rebuilt = build_simulated_route_path(fir_entry, route)
        if len(rebuilt) < 2:
            failures += 1
            _log_error(
                error_type="ROUTE_SEGMENT_MISSING",
                aircraft_id=tid,
                callsign=callsign,
                fir_entry=fir_entry,
                route=route,
            )
            recent.append({"type": "ROUTE_SEGMENT_MISSING", "callsign": callsign, "id": tid})
            continue

        st = _state.setdefault(tid, {"last_along": None, "stuck": 0})
        if sim_active and isinstance(along, (int, float)) and path_total > 0.5:
            prev = st["last_along"]
            along_f = float(along)
            path_f = float(path_total)
            mid_route = along_f < path_f - 0.25
            if prev is not None and mid_route and abs(along_f - float(prev)) < 1e-6:
                st["stuck"] += 1
            else:
                st["stuck"] = 0
            st["last_along"] = along_f
            if st["stuck"] >= stuck_ticks and mid_route:
                failures += 1
                _log_error(
                    error_type="AIRCRAFT_NOT_MOVING",
                    aircraft_id=tid,
                    callsign=callsign,
                    fir_entry=fir_entry,
                    route=route,
                    extra={"along_nm": along, "path_total_nm": path_total, "stuck_ticks": st["stuck"]},
                )
                recent.append({"type": "AIRCRAFT_NOT_MOVING", "callsign": callsign, "id": tid})
                if track is not None:
                    track.last_simulated_at = None
                    db.session.add(track)
                    st["stuck"] = 0
                    _log_error(
                        error_type="STUCK_AUTOFIX_RESET_SIM_CLOCK",
                        aircraft_id=tid,
                        callsign=callsign,
                        fir_entry=fir_entry,
                        route=route,
                    )

        if (
            sim_active
            and isinstance(lat, (int, float))
            and isinstance(lon, (int, float))
            and isinstance(resolved, list)
        ):
            dmin = min_nm_to_resolved_path(float(lat), float(lon), resolved)
            if dmin > corridor:
                failures += 1
                _log_error(
                    error_type="ROUTE_DEVIATION_DETECTED",
                    aircraft_id=tid,
                    callsign=callsign,
                    fir_entry=fir_entry,
                    route=route,
                    extra={"min_nm_to_path": round(dmin, 3), "corridor_nm": corridor},
                )
                recent.append(
                    {"type": "ROUTE_DEVIATION_DETECTED", "callsign": callsign, "id": tid}
                )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("radar_test_monitor commit failed")

    _stats_tick += 1
    _last_stats = {
        "active": active,
        "failures": failures,
        "completed_visible": completed,
        "recent_errors": recent[-12:],
        "tick": _stats_tick,
    }

