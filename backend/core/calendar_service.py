import logging
import os
import pickle
from datetime import datetime, timedelta
from dateutil import parser
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import pytz
from core.validation import is_valid_date, is_valid_time
from core.timezone_utils import parse_datetime, validate_timezone
from rapidfuzz import fuzz,process
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CalendarService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/calendar']
        self.token_path = 'token.pickle'
        self.BUFFER_MINUTES = 15
        self.DEFAULT_MEETING_DURATION = 60  # in minutes
        try:
            self.credentials = self._get_credentials()  
            logger.info("Google Calendar service initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar service: {str(e)}")
            raise Exception(f"Failed to initialize Google Calendar service: {str(e)}")
        # Cached service client
        self._service = None

    def _get_service(self):
        if self._service is None:
            self._service = build('calendar', 'v3', credentials=self.credentials)
        return self._service

    def _get_credentials(self):
        creds = None
    # Check if token.pickle exists first
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
             creds = pickle.load(token)
    
    # If credentials are invalid or don't exist, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
             flow = InstalledAppFlow.from_client_secrets_file(
                './config/credentials.json', self.SCOPES)
             creds = flow.run_local_server(port=8080)
        
        # Save credentials for future use
        with open(self.token_path, 'wb') as token:
            pickle.dump(creds, token)
    
        return creds

    def _parse_datetime_string(self, datetime_str: str) -> datetime:
        """
        Parse datetime string from Google Calendar API, handling 'Z' suffix for UTC.
        Google Calendar returns strings like '2025-10-03T08:30:00Z'
        """
        if datetime_str.endswith('Z'):
            # Replace 'Z' with '+00:00' for UTC timezone
            datetime_str = datetime_str[:-1] + '+00:00'
        return datetime.fromisoformat(datetime_str)


    def has_conflict_with_buffer(self, existing_events, new_start, new_end):
        for event in existing_events:
            start = event['start'].get('dateTime') or event['start'].get('date')
            end = event['end'].get('dateTime') or event['end'].get('date')
    
            if not start or not end:
                continue  # skip malformed/all-day events
    
            existing_start = self._parse_datetime_string(start)
            existing_end = self._parse_datetime_string(end)
    
            if existing_start.tzinfo is None or existing_end.tzinfo is None:
                raise ValueError("Existing event times must be timezone-aware")
    
            # Normalize to same tz as new_start
            existing_start = existing_start.astimezone(new_start.tzinfo)
            existing_end = existing_end.astimezone(new_start.tzinfo)
    
            logger.debug(f"Checking conflict: new [{new_start} - {new_end}] "
                         f"vs existing [{existing_start} - {existing_end}]")
    
            overlap = not (
                new_end <= existing_start - timedelta(minutes=self.BUFFER_MINUTES) or
                new_start >= existing_end + timedelta(minutes=self.BUFFER_MINUTES)
            )
    
            if overlap:
                return True
    
        return False   

    def suggest_next_slot(self, existing_events, desired_start, duration_minutes):
        current = desired_start
        for event in sorted(existing_events, key=lambda e: e['start'].get('dateTime')):
            start_str = event['start'].get('dateTime')
            end_str = event['end'].get('dateTime')

            if start_str and end_str:
                existing_start = self._parse_datetime_string(start_str)
                existing_end = self._parse_datetime_string(end_str)

                if existing_start.tzinfo is None or existing_end.tzinfo is None:
                    raise ValueError("Existing event times must be timezone-aware")

                if current + timedelta(minutes=duration_minutes) <= existing_start - timedelta(minutes=self.BUFFER_MINUTES):
                    return current

                current = max(current, existing_end + timedelta(minutes=self.BUFFER_MINUTES))

        return current

    def suggest_multiple_slots(self, existing_events, desired_start, duration_minutes, num_suggestions=3):
        """
        Suggests multiple alternative time slots when there's a conflict.
        Returns a list of suggested time slots with different strategies.
        """
        suggestions = []
        
        # Strategy 1: Next available slot after the desired time
        next_slot = self.suggest_next_slot(existing_events, desired_start, duration_minutes)
        suggestions.append({
            'start': next_slot,
            'end': next_slot + timedelta(minutes=duration_minutes),
            'strategy': 'next_available',
            'description': 'Next available time slot'
        })
        
        # Strategy 2: Earlier in the same day (if possible)
        same_day_start = desired_start.replace(hour=9, minute=0, second=0, microsecond=0)  # Start from 9 AM
        if same_day_start < desired_start:
            earlier_slot = self._find_available_slot_in_range(
                existing_events, same_day_start, desired_start, duration_minutes
            )
            if earlier_slot and earlier_slot not in [s['start'] for s in suggestions]:
                suggestions.append({
                    'start': earlier_slot,
                    'end': earlier_slot + timedelta(minutes=duration_minutes),
                    'strategy': 'earlier_same_day',
                    'description': 'Earlier the same day'
                })
        
        # Strategy 3: Same time next day
        next_day_slot = desired_start + timedelta(days=1)
        next_day_end = next_day_slot + timedelta(hours=12)  # Check next 12 hours of next day
        next_day_events = self.fetch_existing_events(next_day_slot, next_day_end)
        
        if not self.has_conflict_with_buffer(next_day_events, next_day_slot, next_day_slot + timedelta(minutes=duration_minutes)):
            suggestions.append({
                'start': next_day_slot,
                'end': next_day_slot + timedelta(minutes=duration_minutes),
                'strategy': 'next_day_same_time',
                'description': 'Same time tomorrow'
            })
        else:
            # Find next available slot tomorrow
            tomorrow_available = self.suggest_next_slot(next_day_events, next_day_slot, duration_minutes)
            if tomorrow_available not in [s['start'] for s in suggestions]:
                suggestions.append({
                    'start': tomorrow_available,
                    'end': tomorrow_available + timedelta(minutes=duration_minutes),
                    'strategy': 'next_day_available',
                    'description': 'Next available slot tomorrow'
                })
        
        # Strategy 4: Common meeting times (10 AM, 2 PM, 4 PM) on the same day
        common_times = [10, 14, 16]  # 10 AM, 2 PM, 4 PM
        for hour in common_times:
            common_time_slot = desired_start.replace(hour=hour, minute=0, second=0, microsecond=0)
            if (common_time_slot != desired_start and 
                common_time_slot > datetime.now(desired_start.tzinfo) and
                common_time_slot not in [s['start'] for s in suggestions]):
                
                if not self.has_conflict_with_buffer(existing_events, common_time_slot, common_time_slot + timedelta(minutes=duration_minutes)):
                    suggestions.append({
                        'start': common_time_slot,
                        'end': common_time_slot + timedelta(minutes=duration_minutes),
                        'strategy': 'common_time',
                        'description': f'Popular meeting time ({common_time_slot.strftime("%I:%M %p")})'
                    })
                    if len(suggestions) >= num_suggestions:
                        break
        
        # Remove duplicates and limit to requested number
        unique_suggestions = []
        seen_times = set()
        for suggestion in suggestions:
            time_key = suggestion['start'].strftime("%Y-%m-%d %H:%M")
            if time_key not in seen_times:
                seen_times.add(time_key)
                unique_suggestions.append(suggestion)
                if len(unique_suggestions) >= num_suggestions:
                    break
        
        return unique_suggestions[:num_suggestions]

    def _find_available_slot_in_range(self, existing_events, range_start, range_end, duration_minutes):
        """
        Finds an available slot within a specific time range.
        """
        current = range_start
        
        # Sort events by start time
        sorted_events = sorted(existing_events, key=lambda e: e['start'].get('dateTime', ''))
        
        for event in sorted_events:
            start_str = event['start'].get('dateTime')
            end_str = event['end'].get('dateTime')
            
            if start_str and end_str:
                existing_start = self._parse_datetime_string(start_str)
                existing_end = self._parse_datetime_string(end_str)
                
                # Skip events outside our range
                if existing_end <= range_start or existing_start >= range_end:
                    continue
                
                # Check if there's space before this event
                if current + timedelta(minutes=duration_minutes) <= existing_start - timedelta(minutes=self.BUFFER_MINUTES):
                    if current + timedelta(minutes=duration_minutes) <= range_end:
                        return current
                
                # Move current time to after this event
                current = max(current, existing_end + timedelta(minutes=self.BUFFER_MINUTES))
        
        # Check if there's space at the end of the range
        if current + timedelta(minutes=duration_minutes) <= range_end:
            return current
        
        return None

    def convert_time_to_24hour(self, time_str: str) -> str:
        """
        Convert time string from various formats to 24-hour format (HH:MM).
        Handles: "4:00 PM", "04:00 PM", "16:00", "4:00PM", etc.
        """
        if not time_str:
            raise ValueError("Empty time string")
        
        time_str = time_str.strip()
        
        # List of supported time formats
        time_formats = [
            "%H:%M",        # 24-hour format: "16:00"
            "%I:%M %p",     # 12-hour format with space: "4:00 PM"
            "%I:%M%p",      # 12-hour format without space: "4:00PM"
        ]
        
        for time_format in time_formats:
            try:
                parsed_time = datetime.strptime(time_str, time_format)
                return parsed_time.strftime("%H:%M")  # Always return 24-hour format
            except ValueError:
                continue
        
        raise ValueError(f"Unable to parse time format: {time_str}")

    def schedule_event(self, title, start_dt, end_dt, timezone, attendees=None):
        service = self._get_service()
        try:
            event = {
                'summary': title,
                'start': {'dateTime': start_dt.isoformat(), 'timeZone': timezone},
                'end': {'dateTime': end_dt.isoformat(), 'timeZone': timezone},
                'attendees': []  # Start with an empty list
            }

            # Validate attendees before adding them to the event
            if attendees:
                valid_attendees = []
                for email in attendees:
                    if isinstance(email, str) and '@' in email:
                        valid_attendees.append({'email': email})
                    else:
                        logger.warning(f"Skipping invalid attendee entry: {email}")
                if valid_attendees:
                    event['attendees'] = valid_attendees

            created_event = service.events().insert(calendarId='primary', body=event).execute()
            return created_event
        except Exception as e:
            logger.error(f"Failed to schedule event: {e}", exc_info=True)
            raise e

    # ---- NEW: Cancel / Reschedule helpers ----
    def _build_day_range(self, date_str: str, timezone: str):
        tz = pytz.timezone(timezone)
        start_dt = tz.localize(datetime.strptime(f"{date_str} 00:00", "%Y-%m-%d %H:%M"))
        end_dt = tz.localize(datetime.strptime(f"{date_str} 23:59", "%Y-%m-%d %H:%M"))
        return start_dt, end_dt

    def find_event(self, title: str | None, date_str: str, time_str: str | None, timezone: str):
        """
        Find the best matching event by title/date/time using fuzzy matching.
        Returns the best matching event dict or None.
        """
        try:
            if not date_str:
                raise ValueError("Date is required to find an event")

            tz = pytz.timezone(timezone)

            # Build search window based on given date and time
            if time_str:
                time_24h = self.convert_time_to_24hour(time_str)
                target_start = tz.localize(datetime.strptime(f"{date_str} {time_24h}", "%Y-%m-%d %H:%M"))
                window_start = target_start - timedelta(hours=12)
                window_end = target_start + timedelta(hours=12)
            else:
                window_start = tz.localize(datetime.strptime(f"{date_str} 00:00", "%Y-%m-%d %H:%M"))
                window_end = tz.localize(datetime.strptime(f"{date_str} 23:59", "%Y-%m-%d %H:%M"))
                target_start = window_start

            # Fetch events in that window
            events = self.fetch_existing_events(window_start, window_end, timezone)
            if not events:
                return None

            # If no title given, pick event closest to requested time
            if not title or not title.strip():
                closest_event = min(
                    events,
                    key=lambda e: abs(
                        (self._parse_datetime_string(e['start']['dateTime']) - target_start).total_seconds()
                    )
                )
                return closest_event

            # Normalize title
            query_title = title.strip().lower()

            # Fuzzy match against event titles
            scored_events = []
            for e in events:
                e_title = (e.get('summary') or e.get('title') or "").strip()
                if not e_title:
                    continue
                score = fuzz.ratio(query_title, e_title.lower())
                scored_events.append((score, e))

            if not scored_events:
                return None

            # Sort by best fuzzy score first, then by time proximity
            scored_events.sort(
                key=lambda tup: (
                    -tup[0],  # highest score first
                    abs((self._parse_datetime_string(tup[1]['start']['dateTime']) - target_start).total_seconds())
                )
            )

            best_score, best_event = scored_events[0]

            # Confidence threshold
            if best_score >= 75:
                return best_event
            else:
                logger.warning(
                    f"Low confidence match ({best_score}%) for title '{title}' -> "
                    f"matched with '{best_event.get('summary','')}'"
                )
                return best_event  # still return, but caller should confirm with user

        except Exception as e:
            logger.error(f"Error finding event: {e}", exc_info=True)
            return None    
    def cancel_event_by_id(self, event_id: str) -> bool:
        try:
            service = self._get_service()
            service.events().delete(calendarId='primary', eventId=event_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to cancel event {event_id}: {e}", exc_info=True)
            return False

    def find_event_flexible(self, title: str | None, date_str: str | None, time_str: str | None, timezone: str):
        """
        Flexible finder:
        - If date is provided, delegate to find_event (time optional, title optional)
        - If date is missing:
            - If title provided: search next 30 days and pick the best fuzzy match, preferring upcoming
            - If no title but time provided: search today for closest time, otherwise pick next upcoming
        Returns event dict or None.
        """
        try:
            tz = pytz.timezone(timezone)
            now_tz = datetime.now(tz)

            if date_str:
                return self.find_event(title, date_str, time_str, timezone)

            # Determine window when date is not supplied: now to +30 days
            window_start = now_tz
            window_end = now_tz + timedelta(days=30)
            events = self.fetch_existing_events(window_start, window_end, timezone)
            if not events:
                return None

            # Helper to get event start in tz
            def ev_start(e):
                return self._parse_datetime_string(e['start']['dateTime']).astimezone(tz)

            # If title is provided, fuzzy match across window
            if title and title.strip():
                query_title = title.strip().lower()
                scored = []
                for e in events:
                    e_title = (e.get('summary') or e.get('title') or '').strip()
                    if not e_title:
                        continue
                    score = fuzz.ratio(query_title, e_title.lower())
                    # Prefer soonest upcoming when scores tie
                    scored.append((score, ev_start(e), e))
                if not scored:
                    return None
                scored.sort(key=lambda t: (-t[0], t[1]))
                best = scored[0]
                return best[2]

            # No title. If time is provided, pick closest time today (or next day) to requested time
            if time_str:
                try:
                    t24 = self.convert_time_to_24hour(time_str)
                    target_today = tz.localize(datetime.strptime(f"{now_tz.strftime('%Y-%m-%d')} {t24}", "%Y-%m-%d %H:%M"))
                except Exception:
                    target_today = now_tz
                # Choose event with start closest to target_today but in future
                future_events = [e for e in events if ev_start(e) >= now_tz]
                if not future_events:
                    return None
                closest = min(future_events, key=lambda e: abs((ev_start(e) - target_today).total_seconds()))
                return closest

            # Neither title nor time: choose next upcoming event
            future_events = [e for e in events if ev_start(e) >= now_tz]
            if not future_events:
                return None
            future_events.sort(key=lambda e: ev_start(e))
            return future_events[0]
        except Exception as e:
            logger.error(f"Error in find_event_flexible: {e}", exc_info=True)
            return None

    def cancel_event(self, title: str | None, date: str | None, time: str | None, timezone: str) -> dict:
        ev = self.find_event(title, date, time, timezone) if date else self.find_event_flexible(title, date, time, timezone)
        if not ev:
            return {"status": "not_found", "message": "Could not find a matching event to cancel."}
        ev_id = ev.get('id') or ev.get('eventId')
        if not ev_id:
            return {"status": "error", "message": "Event found but missing id."}
        ok = self.cancel_event_by_id(ev_id)
        if not ok:
            return {"status": "error", "message": "Failed to cancel the event."}
        return {"status": "cancelled", "event": ev}

    def reschedule_event_by_id(self, event_id: str, new_start_dt: datetime, new_end_dt: datetime, timezone: str) -> dict:
        try:
            service = self._get_service()
            body = {
                'start': {'dateTime': new_start_dt.isoformat(), 'timeZone': timezone},
                'end': {'dateTime': new_end_dt.isoformat(), 'timeZone': timezone},
            }
            updated = service.events().patch(calendarId='primary', eventId=event_id, body=body).execute()
            return {"status": "rescheduled", "event": updated}
        except Exception as e:
            logger.error(f"Failed to reschedule event {event_id}: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def reschedule_event(self, title: str | None, date: str | None, time: str | None, timezone: str, new_date: str, new_time: str) -> dict:
        ev = self.find_event(title, date, time, timezone) if date else self.find_event_flexible(title, date, time, timezone)
        if not ev:
            return {"status": "not_found", "message": "Could not find a matching event to reschedule."}
        ev_id = ev.get('id') or ev.get('eventId')
        if not ev_id:
            return {"status": "error", "message": "Event found but missing id."}
        try:
            new_time_24 = self.convert_time_to_24hour(new_time)
            tz = pytz.timezone(timezone)
            new_start = tz.localize(datetime.strptime(f"{new_date} {new_time_24}", "%Y-%m-%d %H:%M"))
            new_end = new_start + timedelta(minutes=self.DEFAULT_MEETING_DURATION)
        except Exception as e:
            return {"status": "error", "message": f"Invalid new date/time: {e}"}

        return self.reschedule_event_by_id(ev_id, new_start, new_end, timezone)

    def intelligent_schedule_handler(self, gpt_data):
        title = gpt_data.get('title')
        date_str = gpt_data.get('date')
        time_str = gpt_data.get('time')
        timezone = gpt_data.get('timezone', 'UTC')
        attendees = gpt_data.get('attendees', [])

        missing_fields = []

        if not title or not title.strip():
            missing_fields.append("title")
        if not date_str or not is_valid_date(date_str):
            missing_fields.append("date")
        if not time_str or not is_valid_time(time_str):
            missing_fields.append("time")
        try:
            validate_timezone(timezone)
        except ValueError:
            missing_fields.append("timezone")

        if missing_fields:
            return {
                'status': 'missing_info',
                'missing': missing_fields,
                'message': f"Missing or invalid fields: {', '.join(missing_fields)}"
            }

        try:
            # Convert time to 24-hour format before parsing
            time_24h = self.convert_time_to_24hour(time_str)
            tz = pytz.timezone(timezone)
            start_dt = tz.localize(datetime.strptime(f"{date_str} {time_24h}", "%Y-%m-%d %H:%M"))
            end_dt = start_dt + timedelta(minutes=self.DEFAULT_MEETING_DURATION)
        except Exception as e:
            return {
                'status': 'error',
                'message': f"Invalid date/time format: {str(e)}"
            }

        check_start = start_dt - timedelta(minutes=self.BUFFER_MINUTES)
        check_end = end_dt + timedelta(minutes=self.BUFFER_MINUTES)
        existing_events = self.fetch_existing_events(check_start, check_end)

        if self.has_conflict_with_buffer(existing_events, start_dt, end_dt):
            # Get multiple suggestions for better user experience
            suggestions = self.suggest_multiple_slots(existing_events, start_dt, self.DEFAULT_MEETING_DURATION, num_suggestions=3)
            
            # Format suggestions for response
            formatted_suggestions = []
            for i, suggestion in enumerate(suggestions, 1):
                formatted_suggestions.append({
                    'option': i,
                    'start': suggestion['start'].strftime("%Y-%m-%d %H:%M"),
                    'end': suggestion['end'].strftime("%Y-%m-%d %H:%M"),
                    'start_formatted': suggestion['start'].strftime("%A, %B %d at %I:%M %p"),
                    'description': suggestion['description'],
                    'strategy': suggestion['strategy']
                })

            return {
                'status': 'conflict',
                'message': 'The requested time slot conflicts with existing meetings',
                'original_request': {
                    'start': start_dt.strftime("%Y-%m-%d %H:%M"),
                    'end': end_dt.strftime("%Y-%m-%d %H:%M"),
                    'start_formatted': start_dt.strftime("%A, %B %d at %I:%M %p")
                },
                'suggestions': formatted_suggestions,
                'timezone': timezone
            }

        created_event = self.schedule_event(title, start_dt, end_dt, timezone, attendees)
        return {
            'status': 'scheduled',
            'start': start_dt.strftime("%Y-%m-%d %H:%M"),
            'end': end_dt.strftime("%Y-%m-%d %H:%M"),
            'timezone': timezone,
            'event_details': created_event,  # Include the full event details
            'link': created_event.get('htmlLink', '') if created_event else ''
        }

    def schedule_suggested_slot(self, original_meeting_data, selected_option):
        """
        Schedules a meeting using one of the previously suggested time slots.
        
        Args:
            original_meeting_data: The original meeting data with title, attendees, etc.
            selected_option: The option number (1, 2, or 3) selected by the user
        """
        try:
            title = original_meeting_data.get('title')
            timezone = original_meeting_data.get('timezone', 'UTC')
            attendees = original_meeting_data.get('attendees', [])
            
            # Get the original requested time to regenerate suggestions
            original_date = original_meeting_data.get('date')
            original_time = original_meeting_data.get('time')
            
            if not all([title, original_date, original_time]):
                return {
                    'status': 'error',
                    'message': 'Missing required meeting information'
                }
            
            # Recreate the original datetime to get fresh suggestions
            time_24h = self.convert_time_to_24hour(original_time)
            tz = pytz.timezone(timezone)
            original_start_dt = tz.localize(datetime.strptime(f"{original_date} {time_24h}", "%Y-%m-%d %H:%M"))
            
            # Get existing events for conflict checking
            check_start = original_start_dt - timedelta(hours=12)
            check_end = original_start_dt + timedelta(days=2)
            existing_events = self.fetch_existing_events(check_start, check_end)
            
            # Generate suggestions again
            suggestions = self.suggest_multiple_slots(existing_events, original_start_dt, self.DEFAULT_MEETING_DURATION, num_suggestions=3)
            
            # Validate selected option
            if selected_option < 1 or selected_option > len(suggestions):
                return {
                    'status': 'error',
                    'message': f'Invalid option selected. Please choose between 1 and {len(suggestions)}'
                }
            
            # Get the selected suggestion
            selected_suggestion = suggestions[selected_option - 1]
            start_dt = selected_suggestion['start']
            end_dt = selected_suggestion['end']
            
            # Double-check for conflicts (in case calendar changed)
            if self.has_conflict_with_buffer(existing_events, start_dt, end_dt):
                return {
                    'status': 'error',
                    'message': 'The selected time slot is no longer available. Please try again.'
                }
            
            # Schedule the event
            created_event = self.schedule_event(title, start_dt, end_dt, timezone, attendees)
            
            return {
                'status': 'scheduled',
                'start': start_dt.strftime("%Y-%m-%d %H:%M"),
                'end': end_dt.strftime("%Y-%m-%d %H:%M"),
                'start_formatted': start_dt.strftime("%A, %B %d at %I:%M %p"),
                'timezone': timezone,
                'event_details': created_event,
                'link': created_event.get('htmlLink', '') if created_event else '',
                'selected_option': selected_option,
                'description': selected_suggestion['description']
            }
            
        except Exception as e:
            logger.error(f"Error scheduling suggested slot: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': f'Failed to schedule the meeting: {str(e)}'
            }



    def fetch_existing_events(self, start_dt, end_dt, timezone='UTC'):
        """
        Fetches raw event data from Google Calendar with all fields required by the Meeting interface.
        """
        try:
            if not isinstance(start_dt, datetime) or not isinstance(end_dt, datetime):
                raise ValueError("start_dt and end_dt must be datetime objects")

            service = build('calendar', 'v3', credentials=self.credentials)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=pytz.UTC)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=pytz.UTC)
        # We are adding all the extra fields to this request
            fields_to_request = (
            "items("
            "summary,"          # title
            "description,"      # description
            "location,"         # location
            "status,"           # status
            "start(dateTime),"  # start time
            "end(dateTime),"    # end time
            "organizer(email)," # organizer
            "creator(email),"   # creator
            "created,"          # created timestamp
            "updated,"          # updated timestamp
            "attendees(email,responseStatus)," # attendees
            "hangoutLink,"      # hangoutLink
            "htmlLink,"         # htmlLink
            "recurrence,"       # recurrence
            "recurringEventId"  # recurringEventId
            ")"
            )
        
            events_result = service.events().list(
            calendarId='primary',
            timeMin=start_dt.isoformat(),
            timeMax=end_dt.isoformat(),
            singleEvents=True,
            orderBy='startTime',
            fields=f"items(summary,start(dateTime),end(dateTime))"
            ).execute()

            return events_result.get('items', [])

        except Exception as e:
            logger.error(f"Error fetching Google Calendar events: {e}", exc_info=True)
            return []

    def get_availability(self, start: str, end: str, timezone: str):
        """
        Processes raw Google event data into the exact format needed by the frontend.
        """
        try:
            validate_timezone(timezone)
            start_dt = parse_datetime(start)
            end_dt = parse_datetime(end)
        
            events = self.fetch_existing_events(start_dt, end_dt, timezone)
            tz = pytz.timezone(timezone)
        
            processed_events = []
            for event in events:
                start_time_aware = parser.parse(event['start']['dateTime'])
                end_time_aware = parser.parse(event['end']['dateTime'])
                processed_event = {
                'id': event.get('id', ''),
                'title': event.get('summary', 'No Title'),
                'description': event.get('description', ''),
                'location': event.get('location', ''),
                'status': event.get('status', 'confirmed'),
                'organizer': event.get('organizer', {}).get('email', ''),
                'creator': event.get('creator', {}).get('email', ''), # Added creator
                'created': event.get('created', ''),                 # Added created
                'updated': event.get('updated', ''),                 # Added updated
                'attendees': event.get('attendees', []),
                'hangoutLink': event.get('hangoutLink', ''),
                'htmlLink': event.get('htmlLink', ''),
                'recurrence': event.get('recurrence', []),           # Added recurrence
                'recurringEventId': event.get('recurringEventId', ''), # Added recurringEventId
                'start': start_time_aware.astimezone(tz).isoformat(),
                'end': end_time_aware.astimezone(tz).isoformat(),
                    }
                processed_events.append(processed_event)
            
            return processed_events
        
        except Exception as e:
            logger.error(f"Error in get_availability: {e}", exc_info=True)
        # Return empty list in case of error
            return []

    def list_meetings_for_day(self, date: str, timezone: str):
        """
        Returns a simplified list of meetings for the given date in the user's timezone.
        Output items include: id, title, start_local, end_local.
        """
        try:
            validate_timezone(timezone)
            tz = pytz.timezone(timezone)
            start_dt = tz.localize(datetime.strptime(f"{date} 00:00", "%Y-%m-%d %H:%M"))
            end_dt = tz.localize(datetime.strptime(f"{date} 23:59", "%Y-%m-%d %H:%M"))
            events = self.fetch_existing_events(start_dt, end_dt, timezone)

            items = []
            for e in events:
                st = parser.parse(e['start']['dateTime']).astimezone(tz)
                en = parser.parse(e['end']['dateTime']).astimezone(tz)
                items.append({
                    'id': e.get('id', ''),
                    'title': e.get('summary', 'No Title'),
                    'start_local': st.strftime("%Y-%m-%d %H:%M"),
                    'end_local': en.strftime("%Y-%m-%d %H:%M"),
                })
            return items
        except Exception as e:
            logger.error(f"Error listing meetings for day: {e}", exc_info=True)
            return []

    def format_meetings_day_speech(self, items: list, timezone: str) -> str:
        """
        Builds a concise natural-language summary for TTS.
        """
        if not items:
            return "You have no meetings scheduled for that day."
        lines = []
        for idx, it in enumerate(items, start=1):
            lines.append(f"{idx}. {it['title']} from {it['start_local'].split(' ')[1]} to {it['end_local'].split(' ')[1]}.")
        return "Here are your meetings: " + " ".join(lines)

