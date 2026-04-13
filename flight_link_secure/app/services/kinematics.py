"""Speed and map projection helpers for server-side radar simulation (keep in sync with radar.js geoToSVG)."""
from __future__ import annotations

import math
import re
from typing import Sequence

# Match static/js/radar.js haversineNm Earth radius (nautical miles)
EARTH_RADIUS_NM = 3440.065

# Match geoToSVG bounds and canvas in radar.js
LAT_MIN = 23.0
LAT_MAX = 37.5
LON_MIN = 60.5
LON_MAX = 75.5
SVG_WIDTH = 900.0
SVG_HEIGHT = 650.0
SVG_PADDING = 50.0


def to_rad(d: float) -> float:
    return d * (math.pi / 180.0)


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    d_lat = to_rad(lat2 - lat1)
    d_lon = to_rad(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(to_rad(lat1)) * math.cos(to_rad(lat2)) * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_NM * c


def knots_to_nm_per_sec(knots: float) -> float:
    return float(knots) / 3600.0


def parse_speed_to_knots(speed_field: str | None) -> int:
    """Match radar.js parseSpeedToKnots."""
    if not speed_field or not isinstance(speed_field, str):
        return 450
    s = speed_field.strip().upper()
    n = re.match(r"^N(\d{3,5})$", s)
    if n:
        return int(n.group(1), 10)
    m = re.match(r"^M(\d{3})$", s)
    if m:
        mach = int(m.group(1), 10) / 1000.0
        return max(200, round((480 * mach) / 0.82))
    k = re.match(r"^K(\d{3,5})$", s)
    if k:
        return round(int(k.group(1), 10) / 1.852)
    return 450


def latlon_to_svg_xy(lat: float, lon: float) -> tuple[float, float]:
    """Same mapping as radar.js geoToSVG (viewBox user space)."""
    nx = (lon - LON_MIN) / (LON_MAX - LON_MIN)
    ny = (lat - LAT_MIN) / (LAT_MAX - LAT_MIN)
    x = SVG_PADDING + nx * (SVG_WIDTH - 2 * SVG_PADDING)
    y = SVG_HEIGHT - SVG_PADDING - ny * (SVG_HEIGHT - 2 * SVG_PADDING)
    return x, y


def cumulative_nm_polyline(points: Sequence[tuple[float, float]]) -> tuple[list[float], float]:
    cumulative: list[float] = [0.0]
    total = 0.0
    for i in range(1, len(points)):
        la, lo = points[i - 1]
        lb, lo2 = points[i]
        total += haversine_nm(la, lo, lb, lo2)
        cumulative.append(total)
    return cumulative, total


def interpolate_along_polyline(
    points: Sequence[tuple[float, float]],
    cumulative: Sequence[float],
    distance_nm: float,
) -> tuple[float, float]:
    if not points:
        return 0.0, 0.0
    if distance_nm <= 0:
        return points[0][0], points[0][1]
    max_d = cumulative[-1]
    if distance_nm >= max_d:
        return points[-1][0], points[-1][1]
    i = 0
    while i < len(cumulative) - 1 and cumulative[i + 1] < distance_nm:
        i += 1
    seg_start = cumulative[i]
    seg_end = cumulative[i + 1]
    t = (distance_nm - seg_start) / (seg_end - seg_start) if seg_end > seg_start else 0.0
    a_lat, a_lon = points[i]
    b_lat, b_lon = points[i + 1]
    return (
        a_lat + (b_lat - a_lat) * t,
        a_lon + (b_lon - a_lon) * t,
    )
