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
    Checks for missing meeting details, asks the user for them, and stores partial progress.
    Returns the complete entities dictionary when all info is gathered, otherwise returns None.
    """
    from main import send_audio_response
    # Combine new entities with any partial details stored in the session
    partial_details = session.get('partial_meeting_details', {})
    combined_details = {**partial_details, **entities}

    # Check for missing required fields
    for field in REQUIRED_FIELDS:
        value = combined_details.get(field)
        
        # Use validation functions for date and time
        is_invalid = False
        if field == 'date' and (not value or not is_valid_date(value)):
            is_invalid = True
        elif field == 'time' and (not value or not is_valid_time(value)):
            is_invalid = True
        elif not value:
            is_invalid = True

        if is_invalid:
            # If a field is missing or invalid:
            # 1. Store the valid progress we have so far in the session.
            session['partial_meeting_details'] = combined_details
            
            # 2. Ask the user for the missing piece.
            await send_clarification_request(field, websocket, text_to_voice, session)
            
            # 3. Return None to signal that the conversation is ongoing and we should wait.
            return None

    # If all fields are present and valid:
    # 1. Clear the partial details from the session.
    session.pop('partial_meeting_details', None)
    
    # 2. Return the complete details to proceed with scheduling.
    return combined_details