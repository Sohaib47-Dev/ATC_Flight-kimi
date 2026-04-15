"""
Shared validation helpers for ICAO-related core identifiers.
"""
from __future__ import annotations

import re
from typing import Tuple

# ICAO flight-plan item 7 (aircraft identification) practical strict profiles:
# - Airline operations: 3-letter ICAO designator + 1-4 alnum suffix (e.g. PIA777, AIC52A)
# - General aviation registration-style: non-hyphen compact forms commonly filed in item 7
#   (e.g. N123AB, APABC, CGBZR, GABCD)
_CALLSIGN_AIRLINE_RE = re.compile(r"^[A-Z]{3}[A-Z0-9]{1,4}$")
_CALLSIGN_GA_N_RE = re.compile(r"^N\d{1,5}[A-Z]{0,2}$")
_CALLSIGN_GA_REG_RE = re.compile(r"^[A-Z]{1,2}[A-Z0-9]{2,6}$")

# ICAO Doc 8643 aircraft type designator is typically 2-4 alphanumeric characters.
_AIRCRAFT_TYPE_RE = re.compile(r"^[A-Z][A-Z0-9]{1,3}$")
_ICAO_AIRPORT_RE = re.compile(r"^[A-Z]{4}$")


def normalize_icao_token(value: str) -> str:
    return (value or "").strip().upper()


def validate_callsign(value: str) -> Tuple[bool, str]:
    callsign = normalize_icao_token(value)
    if not callsign:
        return False, "Callsign is required."
    if len(callsign) < 3 or len(callsign) > 7:
        return False, "Callsign must be 3 to 7 characters."
    if not callsign.isalnum():
        return False, "Callsign must contain only letters and digits."
    if (
        _CALLSIGN_AIRLINE_RE.fullmatch(callsign)
        or _CALLSIGN_GA_N_RE.fullmatch(callsign)
        or _CALLSIGN_GA_REG_RE.fullmatch(callsign)
    ):
        return True, ""
    return False, "Callsign must match ICAO airline or general aviation format."


def validate_aircraft_type(value: str) -> Tuple[bool, str]:
    aircraft_type = normalize_icao_token(value)
    if not aircraft_type:
        return False, "Aircraft type is required."
    if not _AIRCRAFT_TYPE_RE.fullmatch(aircraft_type):
        return False, "Aircraft type must be a valid 2-4 character ICAO designator."
    if aircraft_type == "ZZZZ":
        return False, "Aircraft type ZZZZ is not allowed in this workflow."
    return True, ""


def validate_icao_airport(value: str, field_name: str = "Airport code") -> Tuple[bool, str]:
    airport = normalize_icao_token(value)
    if not airport:
        return False, f"{field_name} is required."
    if not _ICAO_AIRPORT_RE.fullmatch(airport):
        return False, f"{field_name} must be a 4-letter ICAO code."
    return True, ""

