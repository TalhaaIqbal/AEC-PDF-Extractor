"""
Civil Engineering Data Validator
Validates civil-specific data like stations, match lines, etc.
"""
import re
from typing import Dict, Any, List, Optional


def parse_station(station_str: str) -> Optional[float]:
    """
    Parse station string to numeric value for comparison
    Examples: "25+60.00" -> 2560.00, "0+00.00" -> 0.00
    
    Args:
        station_str: Station string in format ##+##.##
    
    Returns:
        Numeric station value or None if invalid
    """
    try:
        # Handle various station formats
        station_str = station_str.replace("STA", "").strip()
        
        # Split by + sign
        if "+" in station_str:
            parts = station_str.split("+")
            if len(parts) == 2:
                main_station = float(parts[0]) * 100  # Convert to consistent units
                sub_station = float(parts[1])
                return main_station + sub_station
        
        # Try direct conversion
        return float(station_str)
    except (ValueError, AttributeError):
        return None


def is_between_match_lines(station_value: float, match_lines: List[Dict[str, Any]]) -> bool:
    """
    Check if a station value falls within the defined match lines
    
    Args:
        station_value: Numeric station value
        match_lines: List of match line dictionaries with from_station and to_station
    
    Returns:
        True if station is within match line range, False otherwise
    """
    if not match_lines:
        return True  # No match lines defined, so any station is valid
    
    for match_line in match_lines:
        from_station = parse_station(match_line.get("from_station", ""))
        to_station = parse_station(match_line.get("to_station", ""))
        
        if from_station is not None and to_station is not None:
            if from_station <= station_value <= to_station:
                return True
    
    return False


def validate_civil_data(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate civil-specific data and add warnings for invalid entries
    
    Args:
        result: Page analysis result dictionary
    
    Returns:
        Validated result with added warnings for invalid data
    """
    match_lines = result.get("match_lines", [])
    stations = result.get("stations", [])
    
    # Validate stations fall between match lines
    for station in stations:
        station_str = station.get("station", "")
        station_value = parse_station(station_str)
        
        if station_value is not None:
            if not is_between_match_lines(station_value, match_lines):
                station["confidence"] = "low"
                station["warning"] = f"Station {station_str} outside match line range"
        
        # Validate offset format
        offset = station.get("offset", "")
        if offset and not re.match(r'^\+[\d.]+,\s*[\d.]+\s*(LT|RT)?$', offset):
            station["warning"] = f"Offset format may be invalid: {offset}"
    
    # Validate curb/gutter types
    valid_curb_types = ["C&G", "SDK", "CURB", "GUTTER"]
    for curb in result.get("curb_gutter", []):
        curb_type = curb.get("type", "")
        if curb_type and curb_type.upper() not in valid_curb_types:
            curb["warning"] = f"Unusual curb type: {curb_type}"
    
    # Validate right-of-way types
    valid_row_types = ["R/W", "PROP.", "PROPERTY", "EXIST.", "EXISTING"]
    for row in result.get("right_of_way", []):
        row_type = row.get("type", "")
        if row_type and row_type.upper() not in valid_row_types:
            row["warning"] = f"Unusual R/W type: {row_type}"
    
    return result


def validate_civil_consolidation(final_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate consolidated civil results
    
    Args:
        final_result: Final consolidated result dictionary
    
    Returns:
        Validated result with warnings for inconsistencies
    """
    # Check for station continuity across pages
    stations = final_result.get("stations", [])
    if stations:
        station_values = []
        for station in stations:
            station_value = parse_station(station.get("station", ""))
            if station_value is not None:
                station_values.append(station_value)
        
        if station_values:
            station_values.sort()
            # Check for gaps or duplicates
            for i in range(1, len(station_values)):
                gap = station_values[i] - station_values[i-1]
                if gap > 500:  # Large gap might indicate missing stations
                    final_result["warning"] = f"Large station gap detected: {gap}"
                    break
    
    return final_result
