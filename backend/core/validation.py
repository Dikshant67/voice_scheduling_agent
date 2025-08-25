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
    Validates time string in multiple formats:
    - 24-hour format: "14:30", "09:00"
    - 12-hour format with AM/PM: "2:30 PM", "09:00 AM", "05:00 AM"
    """
    if not time_str:
        return False
    
    time_str = time_str.strip()
    
    # List of supported time formats
    time_formats = [
        "%H:%M",        # 24-hour format: "14:30"
        "%I:%M %p",     # 12-hour format with AM/PM: "2:30 PM"
        "%I:%M%p",      # 12-hour format without space: "2:30PM"
    ]
    
    for time_format in time_formats:
        try:
            datetime.strptime(time_str, time_format)
            return True
        except ValueError:
            continue
    
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