"""
Flight Plan Parser - Two-Layer Architecture
Layer 1: Regex Candidate Extraction (Syntax Layer)
Layer 2: Context / Semantic Validation Layer (Logic Layer)
"""
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# Pakistan FIR Entry Points
PAKISTAN_FIR_ENTRY_POINTS = [
    'SULOM', 'MERUN', 'VIKIT', 'GUGAL', 'PURPA', 'BIROS',
    'DODAT', 'SIRKA', 'TELEM', 'REGET',
]


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
        callsign_match = re.search(r'\(FPL-([A-Z0-9]+)-', normalized)
        if callsign_match:
            candidates['callsign'].append(callsign_match.group(1))
        
        # Extract aircraft type candidates from -TYPE/WTC pattern
        # Matches patterns like -B77W/H, -A320/M, -A359/H
        type_matches = re.findall(r'-([A-Z0-9]{2,4})/[A-Z]', normalized)
        candidates['aircraft_types'].extend(type_matches)
        
        # Extract speed candidates (N followed by 4 digits or M followed by 3 digits)
        speed_matches = re.findall(r'\b(N\d{4}|M\d{3}|K\d{4})\b', normalized)
        candidates['speeds'].extend(speed_matches)
        
        # Extract all aerodrome + time pairs (4-letter ICAO + 4-digit time)
        # Look for patterns like OPLA2300, OPKC0500
        ad_matches = re.findall(r'\b([A-Z]{4})(\d{4})\b', normalized)
        candidates['aerodrome_times'].extend(ad_matches)
        
        # Extract route string (everything between aircraft info and destination)
        # Route typically starts after speed/level info
        route_match = re.search(r'-[NMK]\d{3,4}[FAWS]\d{3,4}\s+(.+?)(?:\s+-|$)', normalized)
        if route_match:
            candidates['route'] = route_match.group(1).strip()
        else:
            # Alternative: extract between aircraft type and first aerodrome
            route_alt = re.search(r'/[A-Z]\s+(.+?)(?:\s+[A-Z]{4}\d{4})', normalized)
            if route_alt:
                candidates['route'] = route_alt.group(1).strip()
        
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
            return candidates['callsign'][0]
        
        # Fallback: search for FPL pattern
        match = re.search(r'FPL-([A-Z0-9]+)', normalized)
        if match:
            return match.group(1)
        
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
            if re.match(r'^[A-Z]\d{2,3}[A-Z]?$', aircraft_type):
                return aircraft_type
        
        # Check candidates if direct match fails
        for candidate in candidates['aircraft_types']:
            if re.match(r'^[A-Z]\d{2,3}[A-Z]?$', candidate):
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
            departure = valid_pairs[0][0]
        
        if len(valid_pairs) >= 2:
            destination = valid_pairs[1][0]
        
        return departure, destination
    
    def _extract_fir_entry(self, normalized: str, candidates: Dict) -> Optional[str]:
        """
        Extract Pakistan FIR entry point
        Match against hardcoded list, first match only
        """
        # Check for Pakistan FIR entry points in the route
        for entry_point in PAKISTAN_FIR_ENTRY_POINTS:
            if entry_point in normalized:
                return entry_point
        
        return None
    
    def _extract_speed(self, normalized: str, candidates: Dict) -> Optional[str]:
        """
        Extract speed from flight plan
        Format: N0450 (knots), M082 (Mach), K0850 (km/h)
        """
        if candidates['speeds']:
            return candidates['speeds'][0]
        
        # Fallback search
        match = re.search(r'\b(N\d{4}|M\d{3}|K\d{4})\b', normalized)
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
    if not callsign:
        return False
    # Callsign should be alphanumeric, 2-7 characters
    return bool(re.match(r'^[A-Z0-9]{2,7}$', callsign.upper()))


def get_pakistan_fir_entries() -> List[str]:
    """Return list of Pakistan FIR entry points"""
    return PAKISTAN_FIR_ENTRY_POINTS.copy()
