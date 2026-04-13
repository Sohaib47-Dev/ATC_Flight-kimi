"""
Auto-seed defense radar with one synthetic track per Pakistan FIR entry point.

Enabled when ``RADAR_TEST_AUTO_SEED`` is true (see ``DevelopmentConfig``). Idempotent:
if any ``RTST%`` flight plan exists, the whole seed is skipped once per process.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime

from flask import Flask
from sqlalchemy import or_

from app.extensions import db
from app.models import FlightPlan, TrackData, User
from modules.flight_plan_parser import FlightPlanParser, get_pakistan_fir_entries

logger = logging.getLogger(__name__)

_seed_lock = threading.Lock()
_seed_attempted = False


def _raw_fpl(callsign: str, fir_entry: str, route_suffix: str) -> str:
    return (
        f"(FPL-{callsign}-IS\n"
        "-A320/M\n"
        "-OPLA2300\n"
        f"-N0450F350 {fir_entry} {route_suffix}\n"
        "-EGLL0500)"
    )


def try_auto_seed(app: Flask) -> dict:
    global _seed_attempted
    if not app.config.get("RADAR_TEST_AUTO_SEED"):
        return {"ok": True, "skipped": True, "reason": "RADAR_TEST_AUTO_SEED off"}

    with _seed_lock:
        if _seed_attempted:
            return {"ok": True, "skipped": True, "reason": "already_attempted"}
        _seed_attempted = True

    route_suffix = "M875 M881 LAJAK"
    entries = get_pakistan_fir_entries()
    created = 0
    errors: list[str] = []

    with app.app_context():
        if FlightPlan.query.filter(FlightPlan.callsign.like("RTST%")).first():
            logger.info("radar_test_seed: RTST flight plans already present; skip")
            return {"ok": True, "skipped": True, "reason": "rtst_plans_exist"}

        user = User.query.filter(or_(User.role == "defense", User.role == "admin")).first()
        if not user:
            logger.warning("radar_test_seed: no defense/admin user; skipping")
            return {"ok": False, "skipped": True, "reason": "no_user"}

        parser = FlightPlanParser()
        for idx, fir_entry in enumerate(entries):
            callsign = f"RTST{idx:02d}"[:7]
            raw = _raw_fpl(callsign, fir_entry, route_suffix)
            parsed = parser.parse(raw)
            if not parsed:
                err = f"{callsign}/{fir_entry}: parse failed {parser.get_errors()}"
                errors.append(err)
                logger.warning("radar_test_seed: %s", err)
                continue

            fp = FlightPlan(callsign=callsign, raw_flight_plan=raw)
            db.session.add(fp)
            db.session.flush()

            pd = parsed.to_dict()
            track = TrackData(
                flight_plan_id=fp.id,
                callsign=pd.get("callsign", callsign),
                aircraft_type=pd.get("aircraft_type", "A320"),
                departure=pd.get("departure", "OPLA"),
                destination=pd.get("destination", "EGLL"),
                fir_entry=pd.get("fir_entry", fir_entry),
                speed=pd.get("speed", "N0450"),
                route=pd.get("route", ""),
                eto_utc="0000",
                eto_pst="0500",
                cfl="350",
                ssr=f"{(7100 + idx) % 10000:04d}",
                status="active",
                sent_to_defense=True,
                sent_at=datetime.utcnow(),
                created_by=user.id,
            )
            db.session.add(track)
            created += 1

        if created:
            db.session.commit()
            logger.info("radar_test_seed: created %s synthetic FIR-entry tracks", created)
        else:
            db.session.rollback()

    return {"ok": True, "created": created, "errors": errors}
