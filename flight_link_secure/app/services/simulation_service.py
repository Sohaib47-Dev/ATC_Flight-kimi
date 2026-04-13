"""
Server-authoritative radar track advancement and API payload for defense radar.

Persists progress in TrackData.current_position JSON:
  { "lat", "lon", "along_nm", "path_hash", "x", "y" }

Uses TrackData.last_simulated_at for dt integration (wall seconds, capped).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from flask import Flask, current_app

from app.extensions import db
from app.models import TrackData
from app.services.defense_service import list_active_defense_tracks
from app.services.kinematics import (
    cumulative_nm_polyline,
    interpolate_along_polyline,
    knots_to_nm_per_sec,
    latlon_to_svg_xy,
    parse_speed_to_knots,
)
from app.services.route_builder import build_simulated_route_path, path_fingerprint
from app.services.separation_engine import TrackSnapshot, find_conflict_ids

_DT_CAP_SEC = 300.0
logger = logging.getLogger(__name__)


def _config_bool(key: str, default: bool = False) -> bool:
    try:
        v = current_app.config.get(key, default)
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("1", "true", "yes", "on")
    except RuntimeError:
        pass
    return default


def _config_float(key: str, default: float = 1.0) -> float:
    try:
        return float(current_app.config.get(key, default))
    except (RuntimeError, TypeError, ValueError):
        return default


def _parse_eto_utc_datetime(eto_utc: str | None, ref: datetime) -> datetime | None:
    if eto_utc is None or eto_utc == "":
        return None
    s = re.sub(r"\D", "", str(eto_utc)).zfill(4)[-4:]
    if len(s) < 4:
        return None
    hh = int(s[:2], 10)
    mm = int(s[2:4], 10)
    if hh > 23 or mm > 59:
        return None
    r = ref.astimezone(timezone.utc) if ref.tzinfo else ref.replace(tzinfo=timezone.utc)
    return r.replace(hour=hh, minute=mm, second=0, microsecond=0)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _load_sim_state(track: TrackData) -> dict[str, Any]:
    if not track.current_position:
        return {}
    try:
        return json.loads(track.current_position)
    except (json.JSONDecodeError, TypeError):
        return {}


def _advance_track(track: TrackData, now: datetime) -> dict[str, Any]:
    """
    Update track sim state in-place. Returns snapshot fields for separation + API.
    """
    now_utc = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    use_eto = _config_bool("RADAR_SIM_USE_ETO", False)
    eto_bypass = _config_bool("RADAR_SIM_ETO_BYPASS", True)

    path = build_simulated_route_path(track.fir_entry, track.route)
    fp = path_fingerprint(path) if path else ""

    state = _load_sim_state(track)
    along = float(state.get("along_nm", 0.0))
    if state.get("path_hash") != fp:
        along = 0.0

    cumulative, total_nm = cumulative_nm_polyline(path) if path else ([0.0], 0.0)

    last = track.last_simulated_at or track.created_at
    if last is None:
        last = _naive_utc(_now_utc())
    if last.tzinfo:
        last = last.astimezone(timezone.utc).replace(tzinfo=None)
    now_naive = _naive_utc(now_utc)
    if track.last_simulated_at is None:
        dt = 0.0
    else:
        dt = (now_naive - last).total_seconds()
        dt = min(max(dt, 0.0), _DT_CAP_SEC)

    eto_dt = _parse_eto_utc_datetime(track.eto_utc, now_utc)
    eto_ok = eto_bypass or not use_eto or eto_dt is None or now_utc >= eto_dt

    knots = parse_speed_to_knots(track.speed)
    vis_mult = max(0.0, min(_config_float("RADAR_SIM_VISUAL_MULTIPLIER", 3.0), 50.0))
    if eto_ok and path and total_nm > 0 and (track.status or "").lower() == "active":
        along += knots_to_nm_per_sec(knots) * dt * vis_mult
        if along >= total_nm:
            along = float(total_nm)
            track.status = "completed"
            track.completed_at = now_naive

    if path and total_nm > 0:
        lat, lon = interpolate_along_polyline(path, cumulative, along)
    elif path:
        lat, lon = path[0][0], path[0][1]
    else:
        from app.services.route_builder import resolve_fir_entry_lat_lon

        entry = resolve_fir_entry_lat_lon(track.fir_entry)
        if entry:
            lat, lon = entry
        else:
            lat, lon = 30.5, 70.0

    x, y = latlon_to_svg_xy(lat, lon)
    track.current_position = json.dumps(
        {
            "lat": lat,
            "lon": lon,
            "along_nm": along,
            "path_hash": fp,
            "x": x,
            "y": y,
        }
    )
    track.last_simulated_at = now_naive

    cfl = int("".join(c for c in str(track.cfl or "") if c.isdigit()) or "0", 10)
    sim_active = eto_ok and (track.status or "").lower() == "active"

    return {
        "id": track.id,
        "lat": lat,
        "lon": lon,
        "x": x,
        "y": y,
        "cfl": cfl,
        "sim_active": sim_active,
        "resolved_path": [{"lat": p[0], "lon": p[1]} for p in path],
        "along_nm": along,
        "path_total_nm": total_nm,
    }


def advance_defense_tracks_and_build_payload(app: Flask | None = None) -> list[dict[str, Any]]:
    """
    Advance all active defense tracks, commit, run separation, return JSON rows for GET /api/defense/tracks.
    """
    tracks: list[TrackData] = list_active_defense_tracks()
    now = _now_utc()
    snapshots: list[dict[str, Any]] = []
    for t in tracks:
        snapshots.append(_advance_track(t, now))

    sep_inputs = [
        TrackSnapshot(id=s["id"], lat=s["lat"], lon=s["lon"], cfl=s["cfl"])
        for s in snapshots
        if s.get("sim_active")
    ]
    conflict_ids = find_conflict_ids(sep_inputs)

    out: list[dict[str, Any]] = []
    for track, snap in zip(tracks, snapshots):
        row = track.to_dict()
        row["x"] = snap["x"]
        row["y"] = snap["y"]
        row["conflict"] = track.id in conflict_ids and snap.get("sim_active", False)
        row["resolved_path"] = snap["resolved_path"]
        row["sim_active"] = snap["sim_active"]
        row["sim_source"] = "server"
        row["along_nm"] = snap["along_nm"]
        row["path_total_nm"] = snap["path_total_nm"]
        row["lat"] = snap["lat"]
        row["lon"] = snap["lon"]
        out.append(row)

    db.session.commit()
    try:
        from app.services import radar_test_monitor as radar_test_monitor

        app_obj = app if app is not None else current_app
        radar_test_monitor.process_tick(app_obj, out)
    except Exception:
        logger.exception("radar_test_monitor.process_tick failed")
    return out


def defense_tracks_minimal_ws_payload(full_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Slim payload for Socket.IO ``aircraft_update`` (no resolved_path / large blobs).
    """
    out: list[dict[str, Any]] = []
    for r in full_rows:
        cfl = r.get("cfl")
        if not isinstance(cfl, int):
            cfl = int("".join(c for c in str(r.get("cfl", "") or "") if c.isdigit()) or "0", 10)
        out.append(
            {
                "id": r["id"],
                "lat": r["lat"],
                "lon": r["lon"],
                "cfl": cfl,
                "callsign": r.get("callsign", ""),
                "aircraft_type": r.get("aircraft_type", ""),
                "departure": r.get("departure", ""),
                "destination": r.get("destination", ""),
                "fir_entry": r.get("fir_entry", ""),
                "route": r.get("route") or "",
                "speed": r.get("speed", ""),
                "eto_utc": r.get("eto_utc", ""),
                "ssr": r.get("ssr", ""),
                "created_at": r.get("created_at"),
                "conflict": bool(r.get("conflict")),
                "sim_active": bool(r.get("sim_active", True)),
                "status": r.get("status", "active"),
                "sim_source": "server",
            }
        )
    return out


def ensure_track_last_simulated_column(app) -> None:
    """SQLite: add last_simulated_at if missing (existing DBs)."""
    from sqlalchemy import inspect, text

    engine = db.engine
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    try:
        cols = {c["name"] for c in insp.get_columns("track_data")}
    except Exception:
        return
    if "last_simulated_at" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE track_data ADD COLUMN last_simulated_at DATETIME"))
