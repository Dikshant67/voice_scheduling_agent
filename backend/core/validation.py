from datetime import datetime
import pytz

def is_valid_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def is_valid_time(time_str: str) -> bool:
    try:
        datetime.strptime(time_str, "%H:%M")
        return True
    except ValueError:
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