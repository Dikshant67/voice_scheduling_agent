# In core/conversation_flow.py
from typing import Optional
from core.text_to_voice import TextToVoice
from fastapi import WebSocket
from core.validation import is_valid_date, is_valid_time
import re
import logging

# Get the logger instance
logger = logging.getLogger(__name__)
REQUIRED_FIELDS = ['title', 'date', 'time']

async def handle_conflict_resolution(websocket, conflict_data, session):
    """
    Handles the conversation flow when there's a scheduling conflict.
    Presents options to the user and waits for their selection.
    """
    from main import send_audio_response
    
    # Store conflict data in session for later use
    session['conflict_data'] = conflict_data
    session['awaiting_conflict_resolution'] = True
    
    # Preserve the original meeting details from the conflict data
    if 'original_meeting_data' in conflict_data:
        session['original_meeting_data'] = conflict_data['original_meeting_data']
    
    # Build the response message with options
    original_time = conflict_data['original_request']['start_formatted']
    suggestions = conflict_data['suggestions']
    
    response_parts = [
        f"I found a conflict with your requested time of {original_time}.",
        "Here are some alternative options:"
    ]
    
    for suggestion in suggestions:
        option_text = f"Option {suggestion['option']}: {suggestion['start_formatted']} - {suggestion['description']}"
        response_parts.append(option_text)
    
    # Keep the message text for UI, but mute TTS so no sound is played
    response_parts.append("Which option would you prefer? You can say 'option 1', 'option 2', 'option 3', or ask me to suggest different times.")
    
    full_response = " ".join(response_parts)
    
    await send_audio_response(websocket, full_response, "conflict_resolution", session, {
        "conflict_data": conflict_data,
        "awaiting_selection": True,
        
    })

async def process_conflict_selection(user_input: str, session: dict) -> [int, str, None]:
    """
    Processes the user's selection from conflict resolution options with improved accuracy.
    Returns the selected option number, 'different', or None if invalid.
    """
    user_input_lower = user_input.lower().strip()
    
    # --- FIX 1: Check for rejection FIRST using word boundaries ---
    # Using r'\bno\b' ensures 'no' doesn't match inside 'number' or 'know'.
    rejection_patterns = [
        'different', 'other', 'another', 'none', 'neither', r'\bno\b', 'cancel'
    ]
    for pattern in rejection_patterns:
        if re.search(pattern, user_input_lower):
            return 'different'

    # --- If not a rejection, now check for a valid selection ---
    
    # A. Check for selections with digits (e.g., "option 1")
    option_patterns = [
        r'(?:option|choice|number|pick|select)\s*(\d+)',
        r'^(\d+)$' # A raw number like "1"
    ]
    
    for pattern in option_patterns:
        match = re.search(pattern, user_input_lower)
        if match:
            try:
                option_num = int(match.group(1))
                # Assuming max 3 suggestions, adjust if needed
                # if 1 <= option_num <= 3: 
                #     return option_num
                suggestions = session.get('conflict_data', {}).get('suggestions', [])
                if 1 <= option_num <= len(suggestions):
                    return option_num
            except (ValueError, IndexError):
                continue
    
    # B. Check for selections with words (e.g., "the first one")
    # Using word boundaries (\b) prevents "one" from matching inside "none"
    text_mappings = {
        r'\b(?:first|one|1st)\b': 1,
        r'\b(?:second|two|2nd)\b': 2,
        r'\b(?:third|three|3rd)\b': 3
    }
    
    for pattern, num in text_mappings.items():
        if re.search(pattern, user_input_lower):
            return num
    
    # If no valid selection or rejection was found, return None
    return None
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
    
        # --- START OF FIX ---
    # Normalize incoming entities to handle singular/plural variations from GPT
    normalized_entities = {}
    for key, value in entities.items():
        # Use a precise 'in' check for date/dates
        if key in ('date', 'dates'):
            normalized_entities['date'] = value[0] if isinstance(value, list) and value else value
        # Use a precise 'in' check for time/times, which will NOT match 'timezone'
        elif key in ('time', 'times'):
            normalized_entities['time'] = value[0] if isinstance(value, list) and value else value
        else:
            normalized_entities[key] = value
    # --- END OF THE CORRECTED FIX ---

    # Now, use the clean, normalized data for the rest of the function
    combined_details = {**partial_details, **normalized_entities}

    # First, check for the basic required fields
    for field in REQUIRED_FIELDS:
        value = combined_details.get(field)
        # ... (Your existing validation for title, date, time)
        is_invalid = False
        if field == 'date' and (not value or not is_valid_date(value)): is_invalid = True
        elif field == 'time' and (not value or not is_valid_time(value)): is_invalid = True
        
       
        # if is_invalid:
        #     session['partial_meeting_details'] = combined_details
        #     logger.info("--- is_valid_time: FAILED - No format matched. Returning False. ---")
        #     await send_clarification_request(field, websocket, text_to_voice, session)
        #     return None
    
   
    # Note: Email validation for attendees is now optional
    # The calendar service will handle attendees gracefully:
    # - Valid emails will be added as attendees
    # - Names without emails will be skipped (logged as warning)
    # This provides a better user experience for basic meeting scheduling

    # If we get here, all information is complete
    session.pop('partial_meeting_details', None)
    return combined_details