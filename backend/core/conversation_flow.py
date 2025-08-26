# In core/conversation_flow.py

from typing import Optional
from core.text_to_voice import TextToVoice
from fastapi import WebSocket
from core.validation import is_valid_date, is_valid_time

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

async def process_conflict_selection(user_input: str, session: dict):
    """
    Processes the user's selection from conflict resolution options.
    Returns the selected option number or None if invalid.
    """
    user_input_lower = user_input.lower().strip()
    
    # Extract option number from various formats
    option_patterns = [
        r'option\s*(\d+)',
        r'choice\s*(\d+)',
        r'number\s*(\d+)',
        r'^(\d+)$',  # Just a number
        r'the\s*(\d+)',
        r'pick\s*(\d+)',
        r'select\s*(\d+)'
    ]
    
    import re
    for pattern in option_patterns:
        match = re.search(pattern, user_input_lower)
        if match:
            try:
                option_num = int(match.group(1))
                if 1 <= option_num <= 3:  # Valid option range
                    return option_num
            except ValueError:
                continue
    
    # Handle text-based selections
    text_mappings = {
        'first': 1, 'one': 1, '1st': 1,
        'second': 2, 'two': 2, '2nd': 2,
        'third': 3, 'three': 3, '3rd': 3
    }
    
    for text, num in text_mappings.items():
        if text in user_input_lower:
            return num
    
    # Handle rejection/request for different options
    rejection_keywords = ['different', 'other', 'another', 'none', 'neither', 'no', 'cancel']
    if any(keyword in user_input_lower for keyword in rejection_keywords):
        return 'different'
    
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