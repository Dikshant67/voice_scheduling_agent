# In core/conversation_flow.py

from typing import Optional
from core.text_to_voice import TextToVoice
from fastapi import WebSocket
from core.validation import is_valid_date, is_valid_time

REQUIRED_FIELDS = ['title', 'date', 'time']

async def send_clarification_request(field: str, websocket: WebSocket, text_to_voice: TextToVoice, session: dict):
    """Sends a vocal request for a missing field."""
    prompts = {
        "title": "What should the title of the meeting be?",
        "date": "What date should I schedule that for?",
        "time": "And for what time?",
        
    }
    question = prompts.get(field, f"What is the {field}?")
    
    # This is a helper function from main.py, ensure it exists there
    from main import send_audio_response 
    await send_audio_response(websocket, question, "clarification", session)

async def fill_missing_fields_async(entities: dict, text_to_voice: TextToVoice, websocket: WebSocket, session: dict) -> Optional[dict]:
    """
    Checks for missing details, including attendee emails, and asks the user for them.
    """
    from main import send_audio_response
    partial_details = session.get('partial_meeting_details', {})
    combined_details = {**partial_details, **entities}

    # First, check for the basic required fields
    for field in REQUIRED_FIELDS:
        value = combined_details.get(field)
        # ... (Your existing validation for title, date, time)
        is_invalid = False
        if field == 'date' and (not value or not is_valid_date(value)): is_invalid = True
        elif field == 'time' and (not value or not is_valid_time(value)): is_invalid = True
        elif not value: is_invalid = True
        
        if is_invalid:
            session['partial_meeting_details'] = combined_details
            await send_clarification_request(field, websocket, text_to_voice, session)
            return None

   
    # Note: Email validation for attendees is now optional
    # The calendar service will handle attendees gracefully:
    # - Valid emails will be added as attendees
    # - Names without emails will be skipped (logged as warning)
    # This provides a better user experience for basic meeting scheduling

    # If we get here, all information is complete
    session.pop('partial_meeting_details', None)
    return combined_details