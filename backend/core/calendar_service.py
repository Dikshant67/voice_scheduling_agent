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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')  # Missing closing parenthesis
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

    def has_conflict_with_buffer(self, existing_events, new_start, new_end):
        for event in existing_events:
            start = event['start'].get('dateTime')
            end = event['end'].get('dateTime')

            if start and end:
                existing_start = datetime.fromisoformat(start)
                existing_end = datetime.fromisoformat(end)

                if existing_start.tzinfo is None or existing_end.tzinfo is None:
                    raise ValueError("Existing event times must be timezone-aware")

                if not (new_end <= existing_start - timedelta(minutes=self.BUFFER_MINUTES) or
                        new_start >= existing_end + timedelta(minutes=self.BUFFER_MINUTES)):
                    return True
        return False

    def suggest_next_slot(self, existing_events, desired_start, duration_minutes):
        current = desired_start
        for event in sorted(existing_events, key=lambda e: e['start'].get('dateTime')):
            start_str = event['start'].get('dateTime')
            end_str = event['end'].get('dateTime')

            if start_str and end_str:
                existing_start = datetime.fromisoformat(start_str)
                existing_end = datetime.fromisoformat(end_str)

                if existing_start.tzinfo is None or existing_end.tzinfo is None:
                    raise ValueError("Existing event times must be timezone-aware")

                if current + timedelta(minutes=duration_minutes) <= existing_start - timedelta(minutes=self.BUFFER_MINUTES):
                    return current

                current = max(current, existing_end + timedelta(minutes=self.BUFFER_MINUTES))

        return current

    def schedule_event(self, title, start_dt, end_dt, timezone, attendees=None):
        service = build('calendar', 'v3', credentials=self.credentials)
        try:
            event = {
            'summary': title,
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': timezone},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': timezone},
            'attendees': [] # Start with an empty list
            }

        
        # We validate each attendee before adding them to the event.
            if attendees:
                valid_attendees = []
                for email in attendees:
                # A simple but effective check for a valid email format
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
            tz = pytz.timezone(timezone)
            start_dt = tz.localize(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))
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
            suggested_start = self.suggest_next_slot(existing_events, start_dt, self.DEFAULT_MEETING_DURATION)
            suggested_end = suggested_start + timedelta(minutes=self.DEFAULT_MEETING_DURATION)

            return {
                'status': 'conflict',
                'message': 'Conflicting schedule',
                'suggested_start': suggested_start.strftime("%Y-%m-%d %H:%M"),
                'suggested_end': suggested_end.strftime("%Y-%m-%d %H:%M"),
                'timezone': timezone
            }

        meeting_link = self.schedule_event(title, start_dt, end_dt, timezone, attendees)
        return {
            'status': 'scheduled',
            'start': start_dt.strftime("%Y-%m-%d %H:%M"),
            'end': end_dt.strftime("%Y-%m-%d %H:%M"),
            'timezone': timezone,
            'link': meeting_link
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
            fields="items(summary,start(dateTime),end(dateTime))"
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

