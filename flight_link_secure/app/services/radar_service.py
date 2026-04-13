"""
Radar track queries and future server-side simulation logic.

Centralizes selection of tracks shown on the defense radar and any JSON payloads
derived from them. The filter and serialization match
``defense_service.list_active_defense_tracks`` and :meth:`TrackData.to_dict`, so
routes can adopt this module later without changing the radar frontend.

Geometry helpers snap nominal lat/lon to a FIR polyline (same algorithm as
``static/js/radar.js``) for future API enrichment or server-side simulation.

Read-only paths use :attr:`TrackData.query` only. Use ``app.extensions.db`` when
new features need writes or transactions.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

from app.models import TrackData
from app.services import route_builder


def _sync_waypoints_from_config() -> None:
    """Load waypoint tables from ``config/radar_airways.json`` (single source with radar.js)."""
    global WAYPOINTS, CORRECTED_ENTRY_POINTS
    route_builder.reload_airways_config()
    CORRECTED_ENTRY_POINTS = dict(route_builder.corrected_entry_points())
    WAYPOINTS = dict(route_builder.all_waypoints_latlon())


WAYPOINTS: dict[str, tuple[float, float]] = {}
CORRECTED_ENTRY_POINTS: dict[str, tuple[float, float]] = {}
_sync_waypoints_from_config()


def normalize_fir_entry_key_for_coords(fir_entry: str | None) -> str | None:
    """Match radar.js normalizeFirEntryKeyForCoords (canonical DOBAT; legacy DODAT in routes)."""
    if not fir_entry:
        return None
    k = fir_entry.strip().upper()
    if k == "DODAT":
        return "DOBAT"
    return k


def resolve_fir_entry_lat_lon(fir_entry: str | None) -> tuple[float, float] | None:
    """
    Return corrected (lat, lon) for known FIR entry names, else None.

    Delegates to :mod:`app.services.route_builder` (``config/radar_airways.json``).
    """
    return route_builder.resolve_fir_entry_lat_lon(fir_entry)


def _closest_point_on_segment(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> tuple[float, float, float]:
    """
    Closest point on segment A-B to P in planar (x=lon, y=lat) degree space.

    Returns:
        (qx, qy, dist_sq) with (qx, qy) on the segment as (lon, lat).
    """
    abx = bx - ax
    aby = by - ay
    ab2 = abx * abx + aby * aby
    if ab2 < 1e-18:
        dx, dy = px - ax, py - ay
        return ax, ay, dx * dx + dy * dy
    apx = px - ax
    apy = py - ay
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab2))
    qx = ax + t * abx
    qy = ay + t * aby
    dx, dy = px - qx, py - qy
    return qx, qy, dx * dx + dy * dy


def snap_lat_lon_to_polyline(
    lat: float,
    lon: float,
    polyline: Iterable[tuple[float, float]],
) -> tuple[float, float]:
    """
    Project (lat, lon) onto the closest point on a polyline.

    Vertices are ``(latitude, longitude)`` in order; consecutive pairs are
    segments. Mirrors ``snapLatLonToPolyline`` in ``radar.js``.
    """
    verts = list(polyline)
    if len(verts) < 2:
        return lat, lon
    px, py = lon, lat
    best_lat = lat
    best_lon = lon
    best_d = math.inf
    for i in range(len(verts) - 1):
        la, lo = verts[i]
        lb, lo_b = verts[i + 1]
        ax, ay = lo, la
        bx, by = lo_b, lb
        qx, qy, d2 = _closest_point_on_segment(px, py, ax, ay, bx, by)
        if d2 < best_d:
            best_d = d2
            best_lon, best_lat = qx, qy
    return best_lat, best_lon


def _active_radar_track_filter() -> dict[str, object]:
    """Criteria shared by radar and defense track listings for transferred, live tracks."""
    return {'sent_to_defense': True, 'status': 'active'}


def fetch_active_radar_tracks() -> list[TrackData]:
    """
    Load all track rows that should appear on the defense radar.

    Returns ORM instances for callers that need relationships (e.g. flight plan
    or defense messages) when extending simulation logic.

    Returns:
        List of :class:`TrackData` matching ``sent_to_defense`` and ``status``.
    """
    return TrackData.query.filter_by(**_active_radar_track_filter()).all()


def get_active_tracks_json() -> list[dict[str, Any]]:
    """
    Same payload as ``GET /api/defense/tracks`` (server sim + ``x``, ``y``, ``conflict``).

    Requires a Flask application context for :mod:`app.services.simulation_service`.
    """
    from app.services import simulation_service

    return simulation_service.advance_defense_tracks_and_build_payload()
