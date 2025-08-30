from datetime import datetime
import pytz

def is_valid_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def is_valid_time(time_str: str) -> bool:
    """
    Validates time string in multiple formats, ensuring robustness.
    - "17:00", "5:00 PM", "5:00PM", "5 PM", "5PM", "17"
    """
    # Ensure the input is a non-empty string
    if not isinstance(time_str, str) or not time_str:
        return False
    
    # Standardize input: remove whitespace and convert to uppercase for AM/PM consistency
    time_str = time_str.strip().upper()
    
    # A more comprehensive list of supported time formats
    time_formats = [
        "%H:%M",      # 24-hour format: "17:00"
        "%I:%M %p",   # 12-hour format with space: "5:00 PM"
        "%I:%M%p",    # 12-hour format without space: "5:00PM"
        "%I %p",      # 12-hour format, hour only: "5 PM"
        "%I%p",       # 12-hour format, hour only, no space: "5PM"
        "%H"          # 24-hour format, hour only: "17"
    ]
    
    for time_format in time_formats:
        try:
            # If strptime can parse it with a given format, the time is valid
            datetime.strptime(time_str, time_format)
            return True
        except ValueError:
            # If it fails, just try the next format in the list
            continue
            
    # If the loop finishes without any format matching, the time is invalid
    return False
def validate_meeting_details(entities: dict):
    required = ["title", "date", "time", "timezone"]
    for field in required:
        if field not in entities or not entities[field]:
            raise ValueError(f"Missing or empty {field}")
    if not is_valid_date(entities["date"]):
        raise ValueError("Invalid date format")
    if not is_valid_time(entities["time"]):
        raise ValueError("Invalid time format")
    try:
        pytz.timezone(entities["timezone"])
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError("Invalid timezone")
    return entities