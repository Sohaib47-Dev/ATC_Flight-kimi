"""
Resolve FIR entry + route strings into lat/lon polylines for server-side simulation.

Data source: config/radar_airways.json (keep in sync with static/js/radar.js).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

# flight_link_secure/app/services/route_builder.py -> package root is three parents up
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "radar_airways.json"


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def reload_airways_config() -> None:
    """Tests / hot-reload."""
    _load_raw.cache_clear()


def corrected_entry_points() -> dict[str, tuple[float, float]]:
    raw = _load_raw()["corrected_entry_points"]
    return {k: (float(v[0]), float(v[1])) for k, v in raw.items()}


def fir_reference_markers() -> dict[str, tuple[float, float]]:
    raw = _load_raw()["fir_reference_markers"]
    return {k.upper(): (float(v[0]), float(v[1])) for k, v in raw.items()}


def all_waypoints_latlon() -> dict[str, tuple[float, float]]:
    out = dict(corrected_entry_points())
    out.update(fir_reference_markers())
    return out


def normalize_fir_entry_key(fir_entry: str | None) -> str | None:
    if not fir_entry:
        return None
    k = fir_entry.strip().upper()
    if k == "DODAT":
        return "DOBAT"
    return k


def resolve_fir_entry_lat_lon(fir_entry: str | None) -> tuple[float, float] | None:
    """Corrected table first; nominal overrides; then FIR reference markers (e.g. REGET)."""
    key = normalize_fir_entry_key(fir_entry)
    if not key:
        return None
    corr = corrected_entry_points().get(key)
    if corr:
        return corr[0], corr[1]
    nom = _load_raw().get("entry_points_nominal", {}).get(key)
    if nom:
        return float(nom[0]), float(nom[1])
    ref = fir_reference_markers().get(key)
    if ref:
        return ref[0], ref[1]
    return None


def parse_route_tokens(route_str: str | None) -> list[str]:
    if not route_str or not isinstance(route_str, str):
        return []
    return [t for t in re.split(r"\s+", route_str.strip().upper()) if t and t != "DCT"]


def _airspace_rules() -> dict[str, list[str]]:
    raw = _load_raw()["airspace_route_rules"]
    return {k.upper(): list(v) for k, v in raw.items()}


def _airway_polylines() -> dict[str, list[tuple[float, float]]]:
    raw = _load_raw()["airway_polylines"]
    out: dict[str, list[tuple[float, float]]] = {}
    for aid, verts in raw.items():
        out[aid.upper()] = [(float(p[0]), float(p[1])) for p in verts]
    return out


def _route_anchor_tokens() -> set[str]:
    return {t.upper() for t in _load_raw().get("route_anchors", ["SULOM", "GUGAL", "PURPA"])}


def _airway_slice_start(tokens: list[str], fir_entry: str | None) -> int:
    """First index after FIR entry token, else after first route anchor, else 0."""
    fe = normalize_fir_entry_key(fir_entry)
    if fe:
        for i, t in enumerate(tokens):
            if t == fe:
                return i + 1
    anchors = _route_anchor_tokens()
    for i, t in enumerate(tokens):
        if t in anchors:
            return i + 1
    return 0


_ORIENT_TIE_EPS_NM = 1e-6


def _haversine_nm(a: tuple[float, float], b: tuple[float, float]) -> float:
    from app.services.kinematics import haversine_nm

    return haversine_nm(a[0], a[1], b[0], b[1])


def _trim_polyline_from_anchor(
    ordered: list[tuple[float, float]],
    anchor_ll: tuple[float, float] | None,
) -> list[tuple[float, float]]:
    """Drop vertices before the polyline point nearest ``anchor_ll`` (filed join fix)."""
    if not ordered or anchor_ll is None:
        return ordered
    best_j = min(
        range(len(ordered)),
        key=lambda j: (_haversine_nm(anchor_ll, ordered[j]), j),
    )
    return ordered[best_j:]


def _anchor_ll_for_airway_trim(
    tokens: list[str],
    i: int,
    wps: dict[str, tuple[float, float]],
    prev_ll: tuple[float, float] | None,
) -> tuple[float, float] | None:
    """Named fix before airway, else last point (airway-to-airway join)."""
    if i > 0:
        prev_wp = wps.get(tokens[i - 1])
        if prev_wp:
            return float(prev_wp[0]), float(prev_wp[1])
    if prev_ll is not None:
        return prev_ll
    return None


def flatten_airway_points_for_route_tokens(
    tokens: list[str],
    fir_entry: str | None = None,
) -> list[tuple[float, float]]:
    """
    Expand airway tokens to lat/lon. Each polyline is **bidirectional**: order is chosen by
    proximity of the join point (``prev_ll``, else anchor waypoint, else next route waypoint)
    to the polyline ends; if only a following waypoint exists, orient so the path runs toward it.
    """
    pts: list[tuple[float, float]] = []
    start = _airway_slice_start(tokens, fir_entry)
    rules = _airspace_rules()
    polys = _airway_polylines()
    wps = all_waypoints_latlon()
    prev_ll: tuple[float, float] | None = resolve_fir_entry_lat_lon(fir_entry)

    for i in range(start, len(tokens)):
        tok = tokens[i]
        anchor_ll = _anchor_ll_for_airway_trim(tokens, i, wps, prev_ll)
        look_tok = tokens[i + 1] if i + 1 < len(tokens) else None
        look_wp = wps.get(look_tok) if look_tok else None
        look_ll: tuple[float, float] | None = None
        if look_wp:
            look_ll = (float(look_wp[0]), float(look_wp[1]))
        for aid in rules.get(tok, []):
            poly = polys.get(aid.upper())
            if not poly:
                continue
            ref = prev_ll if prev_ll is not None else anchor_ll
            if ref is not None:
                d0 = _haversine_nm(ref, poly[0])
                d1 = _haversine_nm(ref, poly[-1])
                ordered = list(poly) if d0 <= d1 + _ORIENT_TIE_EPS_NM else list(reversed(poly))
            elif look_ll is not None:
                d0 = _haversine_nm(look_ll, poly[0])
                d1 = _haversine_nm(look_ll, poly[-1])
                ordered = list(poly) if d0 >= d1 else list(reversed(poly))
            else:
                ordered = list(poly)
            ordered = _trim_polyline_from_anchor(ordered, anchor_ll)
            for lat, lon in ordered:
                if pts and abs(pts[-1][0] - lat) < 1e-8 and abs(pts[-1][1] - lon) < 1e-8:
                    continue
                pts.append((lat, lon))
                prev_ll = (lat, lon)
    return pts


def ensure_entry_at_start(
    points: list[tuple[float, float]],
    entry_lat: float,
    entry_lon: float,
) -> list[tuple[float, float]]:
    if not points:
        return [(entry_lat, entry_lon)]
    dist_first = _haversine_nm((entry_lat, entry_lon), points[0])
    if dist_first < 0.5:
        out = list(points)
        out[0] = (entry_lat, entry_lon)
        return out
    return [(entry_lat, entry_lon), *points]


_FALLBACK_SEGMENT_NM = 3.0


def _stretch_single_point_path(
    path: list[tuple[float, float]],
    tokens: list[str],
) -> list[tuple[float, float]]:
    """
    If the path is a single vertex, append a second point so cumulative path length
    is non-zero and server simulation can advance ``along_nm``.
    """
    if len(path) != 1:
        return path
    elat, elon = path[0]
    wps = all_waypoints_latlon()
    for tok in tokens:
        g = wps.get(tok)
        if not g:
            continue
        glat, glon = float(g[0]), float(g[1])
        d = _haversine_nm((elat, elon), (glat, glon))
        if d < 1e-3:
            continue
        t = min(1.0, _FALLBACK_SEGMENT_NM / d)
        nlat = elat + (glat - elat) * t
        nlon = elon + (glon - elon) * t
        if _haversine_nm((elat, elon), (nlat, nlon)) < 1e-6:
            continue
        return [(elat, elon), (nlat, nlon)]
    dlon = (_FALLBACK_SEGMENT_NM / 60.0) / max(0.25, math.cos(math.radians(elat)))
    return [(elat, elon), (elat, elon + dlon)]


def ensure_lajak_at_end(points: list[tuple[float, float]], tokens: list[str]) -> list[tuple[float, float]]:
    if "LAJAK" not in tokens:
        return points
    lj = corrected_entry_points().get("LAJAK")
    if not lj:
        return points
    la, lo = lj[0], lj[1]
    if not points:
        return [(la, lo)]
    last = points[-1]
    if _haversine_nm(last, (la, lo)) < 0.5:
        out = list(points)
        out[-1] = (la, lo)
        return out
    return [*points, (la, lo)]


def build_simulated_route_path(fir_entry: str | None, route_str: str | None) -> list[tuple[float, float]]:
    entry = resolve_fir_entry_lat_lon(fir_entry)
    if not entry:
        return []
    tokens = parse_route_tokens(route_str)
    path = flatten_airway_points_for_route_tokens(tokens, fir_entry)
    elat, elon = entry
    if not path:
        path = [(elat, elon)]
    else:
        path = ensure_entry_at_start(path, elat, elon)
        path = ensure_lajak_at_end(path, tokens)
    path = _stretch_single_point_path(path, tokens)
    return path


def path_fingerprint(path: list[tuple[float, float]]) -> str:
    payload = json.dumps(path, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]
