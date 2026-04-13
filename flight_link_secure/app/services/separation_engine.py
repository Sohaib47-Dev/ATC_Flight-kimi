"""Pairwise separation in NM; same flight level rule matches radar.js ConflictDetector."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.services.kinematics import haversine_nm

SEPARATION_THRESHOLD_NM = 15.0


@dataclass(frozen=True)
class TrackSnapshot:
    id: int
    lat: float
    lon: float
    cfl: int


def _parse_cfl(cfl_field: str | None) -> int:
    if not cfl_field:
        return 0
    n = int("".join(c for c in str(cfl_field) if c.isdigit()) or "0", 10)
    return n if n > 0 else 0


def same_flight_level(a: int, b: int) -> bool:
    if not a or not b:
        return False
    return a == b


def find_conflict_ids(snapshots: Iterable[TrackSnapshot]) -> set[int]:
    """Return every track id that is within SEPARATION_THRESHOLD_NM of another at the same FL."""
    items = [s for s in snapshots if s.lat is not None and s.lon is not None]
    conflict: set[int] = set()
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if not same_flight_level(a.cfl, b.cfl):
                continue
            nm = haversine_nm(a.lat, a.lon, b.lat, b.lon)
            if nm < SEPARATION_THRESHOLD_NM:
                conflict.add(a.id)
                conflict.add(b.id)
    return conflict
