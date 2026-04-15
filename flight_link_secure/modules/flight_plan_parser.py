"""
Flight Plan Parser - Two-Layer Architecture
Layer 1: Regex Candidate Extraction (Syntax Layer)
Layer 2: Context / Semantic Validation Layer (Logic Layer)
"""
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from modules.icao_validation import (
    validate_aircraft_type as icao_validate_aircraft_type,
    validate_callsign as icao_validate_callsign,
    validate_icao_airport as icao_validate_icao_airport,
)

# Pakistan FIR entry fixes (canonical names). Order in this list does **not**
# determine which entry is chosen; :meth:`_extract_fir_entry` walks **route
# tokens** in sequence and returns the first token that appears here.
PAKISTAN_FIR_ENTRY_POINTS = [
    'SULOM', 'MERUN', 'VIKIT', 'GUGAL', 'PURPA', 'BIROS',
    'DOBAT', 'SIRKA', 'TELEM', 'REGET',
    'LAJAK', 'ASSVIB',
]

# Field 15: speed/level as one token after the hyphen (e.g. N0450F350, M082F290).
# N/K: tolerate 3–5 TAS digits (non-ICAO filings like N01220F370 still parse).
# M: keep exactly 3 digits before level so ``M881`` airways are not read as Mach.
# Do not use a global ``M\\d{3}`` speed scan — airway identifiers like M881 match that.
_FIELD15_SPEED_LEVEL_RE = re.compile(
    r"-((?:N|K)\d{3,5}[FAWS]\d{3,4}|M\d{3}[FAWS]\d{3,4})\b"
)
_AERODROME_TIME_RE = re.compile(r"-([A-Z]{4})(\d{4})(?=\s|\)|-|$)")


def _speed_from_field15_speed_level_token(token: str) -> Optional[str]:
    """Return speed portion (N0450, N01220, M082, K0850) from a combined speed/level token."""
    if not token:
        return None
    m = re.match(r"^M(\d{3})([FAWS]\d{3,4})$", token)
    if m:
        return f"M{m.group(1)}"
    m = re.match(r"^([NK])(\d{3,5})([FAWS]\d{3,4})$", token)
    if not m:
        return None
    kind, digits = m.group(1), m.group(2)
    if len(digits) < 3 or len(digits) > 5:
        return None
    return f"{kind}{digits}"


@dataclass
class ParsedFlightPlan:
    """Data class for parsed flight plan"""
    callsign: str
    aircraft_type: str
    departure: str
    destination: str
    fir_entry: str
    speed: str
    route: str
    raw_message: str
    
    def to_dict(self) -> Dict:
        return {
            'callsign': self.callsign,
            'aircraft_type': self.aircraft_type,
            'departure': self.departure,
            'destination': self.destination,
            'fir_entry': self.fir_entry,
            'speed': self.speed,
            'route': self.route,
            'raw_message': self.raw_message
        }


class FlightPlanParser:
    """
    Two-Layer Flight Plan Parser
    Handles ICAO flight plan format variations robustly
    """
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def parse(self, raw_flight_plan: str) -> Optional[ParsedFlightPlan]:
        """
        Main parsing method - two-layer architecture
        """
        self.errors = []
        self.warnings = []
        
        if not raw_flight_plan or not raw_flight_plan.strip():
            self.errors.append("Empty flight plan")
            return None
        
        # Normalize the flight plan
        normalized = self._normalize(raw_flight_plan)
        
        # Layer 1: Extract candidates using regex
        candidates = self._extract_candidates(normalized)
        
        # Layer 2: Apply semantic validation
        result = self._validate_and_select(normalized, candidates)
        
        if result and not self.errors:
            return result
        
        return None
    
    def _normalize(self, raw: str) -> str:
        """Normalize the flight plan for parsing"""
        # Remove extra whitespace
        normalized = ' '.join(raw.split())
        # Convert to uppercase
        normalized = normalized.upper()
        return normalized

    def _route_fallback_between_aerodromes(self, normalized: str) -> str:
        """
        When speed/level regexes miss (odd TAS width, spacing), take field 15 as the
        segment between the first and second ``-ICAO####`` departure/destination blocks.
        """
        matches = list(_AERODROME_TIME_RE.finditer(normalized))
        if len(matches) < 2:
            return ""
        return normalized[matches[0].end() : matches[1].start()].strip()

    def _extract_candidates(self, normalized: str) -> Dict:
        """
        Layer 1: Regex Candidate Extraction
        Extract all possible candidates without making decisions
        """
        candidates = {
            'callsign': [],
            'aircraft_types': [],
            'speeds': [],
            'aerodrome_times': [],
            'route': ''
        }
        
        # Extract callsign from FPL- header
        callsign_match = re.search(r'\(FPL-([A-Z0-9]{3,7})-', normalized)
        if callsign_match:
            candidates['callsign'].append(callsign_match.group(1))
        
        # Extract aircraft type candidates from -TYPE/WTC pattern
        # Matches patterns like -B77W/H, -A320/M, -A359/H
        type_matches = re.findall(r'-([A-Z0-9]{2,4})/[A-Z]', normalized)
        candidates['aircraft_types'].extend(type_matches)
        
        # Speed from field-15 combined token only (avoids M### airway vs Mach ambiguity).
        for m in _FIELD15_SPEED_LEVEL_RE.finditer(normalized):
            sp = _speed_from_field15_speed_level_token(m.group(1))
            if sp:
                candidates["speeds"].append(sp)
                break
        
        # Extract all aerodrome + time pairs (4-letter ICAO + 4-digit time)
        # Look for patterns like OPLA2300, OPKC0500
        ad_matches = re.findall(r'\b([A-Z]{4})(\d{4})\b', normalized)
        candidates['aerodrome_times'].extend(ad_matches)
        
        # Extract route string (everything between aircraft info and destination)
        # Route typically starts after speed/level info
        route_match = re.search(
            r"-((?:N|K)\d{3,5}[FAWS]\d{3,4}|M\d{3}[FAWS]\d{3,4})\s+(.+?)(?:\s+-|$)",
            normalized,
        )
        if route_match:
            candidates["route"] = route_match.group(2).strip()
        else:
            # Alternative: extract between aircraft type and first aerodrome
            route_alt = re.search(r'/[A-Z]\s+(.+?)(?:\s+[A-Z]{4}\d{4})', normalized)
            if route_alt:
                candidates['route'] = route_alt.group(1).strip()
        if not candidates["route"]:
            candidates["route"] = self._route_fallback_between_aerodromes(normalized)

        return candidates
    
    def _validate_and_select(self, normalized: str, candidates: Dict) -> Optional[ParsedFlightPlan]:
        """
        Layer 2: Context / Semantic Validation
        Apply rules to select correct values from candidates
        """
        # Extract callsign
        callsign = self._extract_callsign(normalized, candidates)
        if not callsign:
            self.errors.append("Could not extract callsign")
            return None
        
        # Extract aircraft type
        aircraft_type = self._extract_aircraft_type(normalized, candidates)
        if not aircraft_type:
            self.errors.append("Could not extract aircraft type")
            return None
        
        # Extract departure and destination
        departure, destination = self._extract_departure_destination(normalized, candidates)
        if not departure:
            self.errors.append("Could not extract departure aerodrome")
        if not destination:
            self.errors.append("Could not extract destination aerodrome")
        
        # Extract FIR entry point
        fir_entry = self._extract_fir_entry(normalized, candidates)
        if not fir_entry:
            self.warnings.append("Could not identify Pakistan FIR entry point")
            fir_entry = "UNKNOWN"
        
        # Extract speed
        speed = self._extract_speed(normalized, candidates)
        if not speed:
            self.warnings.append("Could not extract speed, using default")
            speed = "N0450"
        
        # Extract route
        route = candidates.get('route', '')
        
        if self.errors:
            return None
        
        return ParsedFlightPlan(
            callsign=callsign,
            aircraft_type=aircraft_type,
            departure=departure,
            destination=destination,
            fir_entry=fir_entry,
            speed=speed,
            route=route,
            raw_message=normalized
        )
    
    def _extract_callsign(self, normalized: str, candidates: Dict) -> Optional[str]:
        """
        Extract callsign from FPL- header
        Format: (FPL-CALLSIGN-...
        """
        if candidates['callsign']:
            callsign = candidates['callsign'][0]
            ok, _ = icao_validate_callsign(callsign)
            if ok:
                return callsign
            self.errors.append("Invalid callsign format in ICAO header")
            return None
        
        # Fallback: search for FPL pattern
        match = re.search(r'FPL-([A-Z0-9]{3,7})', normalized)
        if match:
            callsign = match.group(1)
            ok, _ = icao_validate_callsign(callsign)
            if ok:
                return callsign
            self.errors.append("Invalid callsign format in ICAO header")
            return None
        
        return None
    
    def _extract_aircraft_type(self, normalized: str, candidates: Dict) -> Optional[str]:
        """
        Extract aircraft type from -TYPE/WTC field
        Must be from the specific field, not generic regex
        """
        # Look for pattern: -TYPE/WTC (e.g., -B77W/H, -A320/M)
        type_match = re.search(r'-([A-Z0-9]{2,4})/[A-Z]', normalized)
        if type_match:
            aircraft_type = type_match.group(1)
            # Validate common aircraft type formats
            valid, _ = icao_validate_aircraft_type(aircraft_type)
            if valid:
                return aircraft_type
        
        # Check candidates if direct match fails
        for candidate in candidates['aircraft_types']:
            valid, _ = icao_validate_aircraft_type(candidate)
            if valid:
                return candidate
        
        return None
    
    def _extract_departure_destination(self, normalized: str, candidates: Dict) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract departure and destination aerodromes
        Rule: First ICAO+time = Departure, Second ICAO+time = Destination
        Destination must be before RALT, ALTN, RMK
        """
        # Find position of keywords that mark end of route
        ralt_pos = normalized.find(' RALT ')
        altn_pos = normalized.find(' ALTN ')
        rmk_pos = normalized.find(' RMK ')
        
        # Find the earliest cutoff position
        cutoff_pos = len(normalized)
        for pos in [ralt_pos, altn_pos, rmk_pos]:
            if pos != -1 and pos < cutoff_pos:
                cutoff_pos = pos
        
        # Filter aerodrome-time pairs before cutoff
        valid_pairs = []
        for icao, time in candidates['aerodrome_times']:
            # Find position of this pair in the string
            pair_str = f"{icao}{time}"
            pos = normalized.find(pair_str)
            if pos != -1 and pos < cutoff_pos:
                valid_pairs.append((icao, time, pos))
        
        # Sort by position in the string
        valid_pairs.sort(key=lambda x: x[2])
        
        departure = None
        destination = None
        
        if len(valid_pairs) >= 1:
            dep = valid_pairs[0][0]
            if icao_validate_icao_airport(dep, "Departure")[0]:
                departure = dep
            else:
                self.errors.append("Departure aerodrome is not a valid ICAO code")
        
        if len(valid_pairs) >= 2:
            dest = valid_pairs[1][0]
            if icao_validate_icao_airport(dest, "Destination")[0]:
                destination = dest
            else:
                self.errors.append("Destination aerodrome is not a valid ICAO code")
        
        return departure, destination

    def _route_tokens(self, route: str) -> List[str]:
        """Uppercase tokens from the route field; skip ``DCT``."""
        if not route or not str(route).strip():
            return []
        return [t for t in str(route).strip().upper().split() if t and t != "DCT"]

    def _extract_fir_entry(self, _normalized: str, candidates: Dict) -> Optional[str]:
        """
        First Pakistan FIR entry fix in **route token order** (speed/level line only).

        ``PAKISTAN_FIR_ENTRY_POINTS`` is the allowed-name set only; the static list
        order does not select the entry. There is no whole-message substring pass,
        so fixes mentioned only outside the route cannot override the filed sequence.
        """
        fir_set = frozenset(PAKISTAN_FIR_ENTRY_POINTS)

        def _canonical_fir_token(t: str) -> str:
            if t == "DODAT":
                return "DOBAT"
            return t

        for tok in self._route_tokens(candidates.get("route") or ""):
            ctok = _canonical_fir_token(tok)
            if ctok in fir_set:
                return ctok
        return None
    
    def _extract_speed(self, normalized: str, candidates: Dict) -> Optional[str]:
        """
        Extract speed from flight plan
        Format: N0450 (knots), M082 (Mach), K0850 (km/h)
        """
        if candidates["speeds"]:
            return candidates["speeds"][0]

        # Second pass: combined token if candidate list was empty (e.g. unusual spacing).
        m = _FIELD15_SPEED_LEVEL_RE.search(normalized)
        if m:
            sp = _speed_from_field15_speed_level_token(m.group(1))
            if sp:
                return sp

        # Standalone knots / km/h only (no global Mach scan — collides with M### airways).
        for pat in (r"\b(N\d{3,5})\b", r"\b(K\d{3,5})\b"):
            match = re.search(pat, normalized)
            if match:
                return match.group(1)

        return None
    
    def get_errors(self) -> List[str]:
        """Return parsing errors"""
        return self.errors
    
    def get_warnings(self) -> List[str]:
        """Return parsing warnings"""
        return self.warnings


# Convenience function for direct parsing
def parse_flight_plan(raw_flight_plan: str) -> Optional[Dict]:
    """
    Parse a raw ICAO flight plan and return extracted fields as dictionary
    """
    parser = FlightPlanParser()
    result = parser.parse(raw_flight_plan)
    
    if result:
        return result.to_dict()
    
    return None


def validate_callsign(callsign: str) -> bool:
    """Validate callsign format"""
    return icao_validate_callsign(callsign)[0]


def get_pakistan_fir_entries() -> List[str]:
    """Return list of Pakistan FIR entry points"""
    return PAKISTAN_FIR_ENTRY_POINTS.copy()
