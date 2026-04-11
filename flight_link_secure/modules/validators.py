"""
ATC Estimate Validation Module
Validates and corrects ETO, CFL, and SSR inputs
"""
import re
import random
from typing import Tuple, Optional, Dict
from datetime import datetime, timedelta


class ATCValidator:
    """Validator for ATC estimate fields"""
    
    # SSR codes that are reserved/invalid
    INVALID_SSR_PREFIXES = ['0000', '1111', '2222', '3333', '4444', '5555', '6666', '7777', '8888', '9999']
    
    @staticmethod
    def validate_cfl(cfl: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validate Cleared Flight Level
        Rules:
        - Must be numeric
        - Must be exactly 3 digits
        - Must be <= 500
        
        Returns: (is_valid, message, corrected_value)
        """
        if not cfl:
            return False, "CFL is required", None
        
        # Remove any non-numeric characters
        cfl_clean = re.sub(r'[^0-9]', '', cfl)
        
        # Check if numeric
        if not cfl_clean.isdigit():
            return False, "CFL must be numeric", None
        
        # Check length
        if len(cfl_clean) != 3:
            return False, f"CFL must be exactly 3 digits (got {len(cfl_clean)})", None
        
        # Check value
        try:
            value = int(cfl_clean)
            if value > 500:
                return False, "CFL must be 500 or less", None
            if value < 10:
                return False, "CFL must be at least 010", None
        except ValueError:
            return False, "Invalid CFL value", None
        
        return True, "Valid", cfl_clean
    
    @staticmethod
    def validate_ssr(ssr: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validate SSR Code
        Rules:
        - Exactly 4 digits
        - No letters
        - No repeated digits (1111, 2222, etc.)
        
        Auto-correction:
        - If repeated digits, generate new SSR starting with 4
        
        Returns: (is_valid, message, corrected_value)
        """
        if not ssr:
            return False, "SSR is required", None
        
        # Remove any non-numeric characters
        ssr_clean = re.sub(r'[^0-9]', '', ssr)
        
        # Check length
        if len(ssr_clean) != 4:
            return False, f"SSR must be exactly 4 digits (got {len(ssr_clean)})", None
        
        # Check for letters in original
        if re.search(r'[A-Za-z]', ssr):
            return False, "SSR cannot contain letters", None
        
        # Check for repeated digits
        if len(set(ssr_clean)) == 1:
            # All digits are the same - auto-correct
            corrected = ATCValidator._generate_ssr()
            return False, f"Invalid SSR (repeated digits): {ssr_clean}", corrected
        
        # Check for other invalid patterns
        if ssr_clean in ['0000', '7777']:
            corrected = ATCValidator._generate_ssr()
            return False, f"Reserved SSR code: {ssr_clean}", corrected
        
        return True, "Valid", ssr_clean
    
    @staticmethod
    def _generate_ssr() -> str:
        """
        Generate a valid SSR code
        Preference for codes starting with 4
        """
        # Try to generate starting with 4
        for _ in range(10):
            # Generate 3 random digits
            digits = [str(random.randint(0, 9)) for _ in range(3)]
            ssr = '4' + ''.join(digits)
            
            # Check not all same digits
            if len(set(ssr)) > 1:
                return ssr
        
        # Fallback: generate any valid 4-digit code
        while True:
            ssr = ''.join([str(random.randint(0, 9)) for _ in range(4)])
            if len(set(ssr)) > 1 and ssr not in ['0000', '7777']:
                return ssr
    
    @staticmethod
    def validate_eto(eto: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Validate Estimated Time Over
        Input in UTC (HHMM format)
        Convert to Pakistan Time (UTC +5)
        
        Returns: (is_valid, message, {'utc': 'HHMM', 'pst': 'HHMM'})
        """
        if not eto:
            return False, "ETO is required", None
        
        # Remove any non-numeric characters
        eto_clean = re.sub(r'[^0-9]', '', eto)
        
        # Check length
        if len(eto_clean) != 4:
            return False, f"ETO must be exactly 4 digits (HHMM format, got {len(eto_clean)})", None
        
        # Validate time
        try:
            hours = int(eto_clean[:2])
            minutes = int(eto_clean[2:])
            
            if hours > 23:
                return False, "Hours must be 00-23", None
            if minutes > 59:
                return False, "Minutes must be 00-59", None
            
        except ValueError:
            return False, "Invalid time format", None
        
        # Convert to Pakistan Time (UTC + 5)
        pst_time = ATCValidator._convert_to_pakistan_time(eto_clean)
        
        return True, "Valid", {
            'utc': eto_clean,
            'pst': pst_time
        }
    
    @staticmethod
    def _convert_to_pakistan_time(utc_time: str) -> str:
        """
        Convert UTC time (HHMM) to Pakistan Standard Time (UTC + 5)
        Handles rollover (e.g., 1900 UTC -> 0000 PST)
        """
        hours = int(utc_time[:2])
        minutes = int(utc_time[2:])
        
        # Add 5 hours for Pakistan Time
        pst_hours = (hours + 5) % 24
        
        # Format as HHMM
        return f"{pst_hours:02d}{minutes:02d}"
    
    @staticmethod
    def validate_all(eto: str, cfl: str, ssr: str) -> Dict:
        """
        Validate all ATC estimate fields
        Returns comprehensive validation result
        """
        result = {
            'valid': True,
            'eto': {'valid': False, 'message': '', 'utc': None, 'pst': None},
            'cfl': {'valid': False, 'message': '', 'value': None},
            'ssr': {'valid': False, 'message': '', 'value': None, 'corrected': None},
            'errors': []
        }
        
        # Validate ETO
        eto_valid, eto_msg, eto_data = ATCValidator.validate_eto(eto)
        result['eto']['valid'] = eto_valid
        result['eto']['message'] = eto_msg
        if eto_data:
            result['eto']['utc'] = eto_data['utc']
            result['eto']['pst'] = eto_data['pst']
        if not eto_valid:
            result['valid'] = False
            result['errors'].append(f"ETO: {eto_msg}")
        
        # Validate CFL
        cfl_valid, cfl_msg, cfl_value = ATCValidator.validate_cfl(cfl)
        result['cfl']['valid'] = cfl_valid
        result['cfl']['message'] = cfl_msg
        result['cfl']['value'] = cfl_value
        if not cfl_valid:
            result['valid'] = False
            result['errors'].append(f"CFL: {cfl_msg}")
        
        # Validate SSR
        ssr_valid, ssr_msg, ssr_value = ATCValidator.validate_ssr(ssr)
        result['ssr']['valid'] = ssr_valid
        result['ssr']['message'] = ssr_msg
        result['ssr']['value'] = ssr_value
        if not ssr_valid:
            result['ssr']['corrected'] = ssr_value
            result['errors'].append(f"SSR: {ssr_msg}")
        
        return result


# Convenience functions
def validate_atc_estimates(eto: str, cfl: str, ssr: str) -> Dict:
    """Validate all ATC estimate fields"""
    validator = ATCValidator()
    return validator.validate_all(eto, cfl, ssr)


def format_time_display(time_str: str) -> str:
    """Format HHMM time for display"""
    if len(time_str) == 4:
        return f"{time_str[:2]}:{time_str[2:]}"
    return time_str
