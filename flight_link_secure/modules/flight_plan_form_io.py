"""
Build and parse ICAO-style (FPL-…) messages for the ATC structured flight plan form.

Output must remain compatible with :class:`modules.flight_plan_parser.FlightPlanParser`.
"""
from __future__ import annotations

import re
from typing import Any

_FIELD15_HEAD_RE = re.compile(
    r"^((?:N|K)\d{3,5}[FAWS]\d{3,4}|M\d{3}[FAWS]\d{3,4})\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)


def _four_digits(s: str) -> str:
    d = re.sub(r"\D", "", s or "")
    return (d + "0000")[:4] if d else "0000"


def default_form_fields() -> dict[str, str]:
    return {
        "callsign": "",
        "flight_rules": "I",
        "type_of_flight": "S",
        "aircraft_type": "",
        "wake_turbulence": "M",
        "equipment": "",
        "departure_aerodrome": "",
        "departure_time_utc": "",
        "cruise_speed": "N0450",
        "flight_level": "F350",
        "route": "",
        "destination_aerodrome": "",
        "destination_time_utc": "",
        "alternate_suffix": "",
        "field_18": "",
        "other_info": "",
    }


_ICAO_AD = re.compile(r"^[A-Z]{4}$")


def build_icao_fpl(fields: dict[str, Any]) -> str:
    """Assemble a multi-line ICAO FPL string from structured fields.

    Required: callsign, aircraft_type, departure_aerodrome, destination_aerodrome, route.
    Other fields use sensible defaults when blank (times default to 0000; speed/level defaults).
    """
    d = default_form_fields()
    for k, v in (fields or {}).items():
        if k in d and v is not None:
            d[k] = str(v)

    cs = d["callsign"].strip().upper()
    if not cs:
        raise ValueError("callsign is required")

    fr = (d["flight_rules"] or "I").strip().upper()[:1] or "I"
    tf = (d["type_of_flight"] or "S").strip().upper()[:1] or "S"
    ac = (d["aircraft_type"] or "").strip().upper()
    if not ac:
        raise ValueError("aircraft_type is required")
    wtc = (d["wake_turbulence"] or "M").strip().upper()[:1] or "M"
    eq = (d["equipment"] or "").strip()

    dep = (d["departure_aerodrome"] or "").strip().upper()[:4]
    if not _ICAO_AD.match(dep):
        raise ValueError("departure_aerodrome must be a 4-letter ICAO code")
    dep_t = _four_digits(d["departure_time_utc"])

    spd = (d["cruise_speed"] or "N0450").strip().upper()
    lvl = (d["flight_level"] or "F350").strip().upper()
    route = (d["route"] or "").strip()
    if not route:
        raise ValueError("route is required")

    dest = (d["destination_aerodrome"] or "").strip().upper()[:4]
    if not _ICAO_AD.match(dest):
        raise ValueError("destination_aerodrome must be a 4-letter ICAO code")
    dest_t = _four_digits(d["destination_time_utc"])
    alt_suf = (d["alternate_suffix"] or "").strip()
    if alt_suf and not alt_suf.startswith(" "):
        alt_suf = " " + alt_suf

    lines: list[str] = [f"(FPL-{cs}-{fr}{tf}"]
    if eq:
        lines.append(f"-{ac}/{wtc}-{eq}")
    else:
        lines.append(f"-{ac}/{wtc}")
    lines.append(f"-{dep}{dep_t}")
    lines.append(f"-{spd}{lvl} {route}".rstrip())
    lines.append(f"-{dest}{dest_t}{alt_suf}".rstrip())

    f18 = (d["field_18"] or "").strip()
    if f18:
        for block in f18.splitlines():
            b = block.strip()
            if not b:
                continue
            lines.append(b if b.startswith("-") else f"-{b}")

    other = (d["other_info"] or "").strip()
    if other:
        for block in other.splitlines():
            b = block.strip()
            if not b:
                continue
            lines.append(b if b.startswith("-") else f"-{b}")

    lines.append(")")
    return "\n".join(lines)


def _split_speed_level(token: str) -> tuple[str, str]:
    t = (token or "").strip().upper()
    if not t:
        return "N0450", "F350"
    m = re.match(r"^(M\d{3})([FAWS]\d{3,4})$", t)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^([NK]\d{3,5})([FAWS]\d{3,4})$", t)
    if m:
        return m.group(1), m.group(2)
    return t, ""


def parse_raw_to_form_fields(raw: str) -> tuple[dict[str, str], list[str]]:
    """
    Best-effort line-oriented parse for the structured form.
    Returns (fields, notes) where notes are non-fatal hints.
    """
    notes: list[str] = []
    out = default_form_fields()
    text = (raw or "").strip()
    if not text:
        return out, ["Empty flight plan"]

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return out, ["Empty flight plan"]

    # First line: (FPL-CS-XX
    first = lines[0].upper()
    first = first.rstrip(")")
    m0 = re.match(r"^\(\s*FPL-([A-Z0-9]+)-([A-Z]{2})\s*$", first)
    if m0:
        out["callsign"] = m0.group(1)
        out["flight_rules"] = m0.group(2)[0]
        out["type_of_flight"] = m0.group(2)[1]
    else:
        m0b = re.match(r"^\(\s*FPL-([A-Z0-9]+)-([A-Z])\s*$", first)
        if m0b:
            out["callsign"] = m0b.group(1)
            out["flight_rules"] = m0b.group(2)
            notes.append("Could not parse flight rules/type (single letter); defaulting type S")
            out["type_of_flight"] = "S"
        else:
            notes.append("Could not parse FPL header line")

    i = 1
    # Aircraft / optional equipment on same line
    if i < len(lines):
        body = lines[i].lstrip("-").strip().upper()
        body = body.rstrip(")")
        m_ac_eq = re.match(r"^([A-Z0-9]{2,4})/([A-Z])-(.+)$", body)
        m_ac_only = re.match(r"^([A-Z0-9]{2,4})/([A-Z])$", body)
        if m_ac_eq:
            out["aircraft_type"] = m_ac_eq.group(1)
            out["wake_turbulence"] = m_ac_eq.group(2)
            out["equipment"] = m_ac_eq.group(3).strip()
            i += 1
        elif m_ac_only:
            out["aircraft_type"] = m_ac_only.group(1)
            out["wake_turbulence"] = m_ac_only.group(2)
            i += 1
        else:
            notes.append("Aircraft type / wake line not recognized; left blank")

    # Optional standalone field-10 line before departure (when not merged with type line)
    if i < len(lines):
        body = lines[i].lstrip("-").strip().upper().rstrip(")")
        is_dep = bool(re.match(r"^[A-Z]{4}\d{4}$", body))
        is_f15 = bool(_FIELD15_HEAD_RE.match(body))
        if not is_dep and not is_f15 and not (out["equipment"] or "").strip():
            out["equipment"] = body
            i += 1

    # Departure aerodrome + time
    if i < len(lines):
        body = lines[i].lstrip("-").strip().upper().rstrip(")")
        m_dep = re.match(r"^([A-Z]{4})(\d{4})$", body)
        if m_dep:
            out["departure_aerodrome"] = m_dep.group(1)
            out["departure_time_utc"] = m_dep.group(2)
            i += 1
        else:
            notes.append("Departure line not in ICAO#### form")

    # Field 15
    if i < len(lines):
        body = lines[i].lstrip("-").strip().rstrip(")")
        m15 = _FIELD15_HEAD_RE.match(body)
        if m15:
            tok = m15.group(1).upper()
            spd, lvl = _split_speed_level(tok)
            out["cruise_speed"] = spd
            out["flight_level"] = lvl or "F350"
            out["route"] = (m15.group(2) or "").strip()
        else:
            out["route"] = body
        i += 1

    # Destination (+ optional suffix before field 18)
    if i < len(lines):
        body = lines[i].lstrip("-").strip()
        body = body.rstrip(")")
        m_dest = re.match(r"^([A-Z]{4})(\d{4})(\s+(.*))?$", body, re.I)
        if m_dest:
            out["destination_aerodrome"] = m_dest.group(1).upper()
            out["destination_time_utc"] = m_dest.group(2)
            suf = (m_dest.group(4) or "").strip()
            if suf:
                out["alternate_suffix"] = suf
        else:
            notes.append("Destination line not parsed")
        i += 1

    # Remaining hyphen lines → field_18 / other
    tail: list[str] = []
    while i < len(lines):
        ln = lines[i].strip().rstrip(")")
        if ln == ")" or not ln:
            i += 1
            continue
        if ln.startswith("-"):
            tail.append(ln[1:].strip())
        else:
            tail.append(ln)
        i += 1

    if tail:
        out["field_18"] = "\n".join(tail)

    return out, notes
