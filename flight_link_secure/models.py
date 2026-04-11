"""
Backward-compatible imports for existing scripts (e.g. modules.sample_data).

Prefer: from app.models import ...
"""
from app.models import (
    db,
    User,
    FlightPlan,
    TrackData,
    SystemLog,
    DefenseMessage,
    init_db,
)

__all__ = [
    "db",
    "User",
    "FlightPlan",
    "TrackData",
    "SystemLog",
    "DefenseMessage",
    "init_db",
]
