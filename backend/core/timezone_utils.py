from datetime import datetime
import pytz

def parse_datetime(time_str: str) -> datetime:
    return datetime.fromisoformat(time_str.replace("Z", "+00:00"))

def validate_timezone(timezone: str) -> pytz.BaseTzInfo:
    try:
        return pytz.timezone(timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError(f"Invalid timezone: {timezone}")