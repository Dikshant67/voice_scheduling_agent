# ==============================================================================
# 1. IMPORTS
# ==============================================================================
from dotenv import load_dotenv
load_dotenv()
import asyncio
import json
import logging
import os
import tempfile
import time
import traceback
import wave
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

import azure.cognitiveservices.speech as speechsdk
import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config.config import Config
from core.calendar_service import CalendarService
from core.conversation_flow import fill_missing_fields_async
from core.run_gpt_agent import GPTAgent
from core.smart_audio_processor import SmartAudioProcessor
from core.text_to_voice import TextToVoice
from core.voice_to_text import enhanced_speech_to_text
# ==============================================================================
# 2. LOGGING SETUP
# ==============================================================================
log_format = '%(asctime)s - %(levelname)s - [Session:%(session_id)s] - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)
logger = logging.getLogger(__name__)

class SessionIdFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, 'session_id'):
            record.session_id = 'SYSTEM'
        return True
logger.addFilter(SessionIdFilter())

# ==============================================================================
# 3. CONSTANTS
# ==============================================================================
SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2

# ==============================================================================
# 4. CONNECTION MANAGER
# ==============================================================================
class ConnectionManager:
    def __init__(self):
        self.active_sessions: Dict[int, Dict[str, Any]] = {}
        self.audio_processors: Dict[int, SmartAudioProcessor] = {}
        self.connection_timestamps: Dict[str, float] = {} # Tracks last connection time per IP
        logger.info("ConnectionManager initialized.")

    async def connect(self, websocket: WebSocket) -> Optional[int]:
        try:
            # 1. Always accept the connection first.
            await websocket.accept()
        except WebSocketDisconnect:
            logger.warning("Client disconnected immediately upon connection.")
            return None

        client_ip = websocket.client.host if websocket.client else "unknown"
        current_time = time.time()
        
        # 2. Perform Rate Limiting check.
        last_connection_time = self.connection_timestamps.get(client_ip, 0)
        if current_time - last_connection_time < 1.0: # Limit to 1 connection per second
            logger.warning(f"RATE LIMIT: Too many connection attempts from IP: {client_ip}")
            await websocket.close(code=1008, reason="Rate limit exceeded. Please wait a moment.")
            return None # Signal that the connection failed
        
        # 3. If the connection is allowed, update the timestamp.
        self.connection_timestamps[client_ip] = current_time

        # 4. Clean up any other old/stale sessions from the same IP address.
        self._cleanup_old_sessions_from_ip(client_ip)
        
        # 5. Create and store the new, valid session.
        session_id = id(websocket)
        self.audio_processors[session_id] = SmartAudioProcessor()
        self.active_sessions[session_id] = {
            'id': session_id,
            'websocket': websocket,
            'client_ip': client_ip, # Store the IP for tracking
            'timezone': 'UTC',
            'is_recording': False,
            'processing_lock': asyncio.Lock(),
            'greeting_sent': False,
            'start_time': current_time,
            'interaction_history': [],
            'partial_meeting_details': {},
            'had_user_speech': False  # Track if we have received any meaningful speech yet
        }
        logger.info(f"New connection established from {client_ip}", extra={"session_id": session_id})
        return session_id

    def _cleanup_old_sessions_from_ip(self, client_ip: str):
        """Finds and disconnects any old sessions from the same IP to prevent orphans."""
        # It's safer to iterate over a copy of the items
        current_sessions = list(self.active_sessions.items())
        
        for session_id, session in current_sessions:
            if session.get('client_ip') == client_ip and session_id != id(session['websocket']):
                logger.warning(f"Cleaning up old session {session_id} from same IP {client_ip}")
                # We can't await in a sync function, so we need to schedule the close
                # For simplicity, we'll just disconnect it from our manager
                self.disconnect(session_id)

    def disconnect(self, session_id: int):
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        if session_id in self.audio_processors:
            del self.audio_processors[session_id]
        logger.info("Connection closed and resources cleaned up", extra={"session_id": session_id})


    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        return self.active_sessions.get(session_id)

    def get_processor(self, session_id: int) -> Optional[SmartAudioProcessor]:
        return self.audio_processors.get(session_id)

manager = ConnectionManager()

# ==============================================================================
# 5. FASTAPI APP SETUP (LIFESPAN, CORS)
# ==============================================================================
services = {}
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("--- Application starting up... ---")
    
    # --- THIS IS THE FIX ---
    # We will initialize each service in its own try/except block
    # to get detailed error messages if one fails.
    
    try:
        config = Config()
        
        # Initialize Calendar Service
        try:
            services["calendar"] = CalendarService()
            # app.state.calender_service = CalendarService()
            logger.info("✅ CalendarService initialized.")
        except Exception as e:
            logger.error(f"❌ CalendarService initialization failed: {e}", exc_info=True)
            # Don't continue if critical services fail
            raise e
        
        # Initialize TextToVoice Service
        logger.info("Initializing TextToVoice service...")
        if not config.azure_speech_key or not config.azure_speech_region:
            raise ValueError("AZURE_SPEECH_KEY or AZURE_SPEECH_REGION is missing from .env file.")
        # services["text_to_voice"] = TextToVoice(config.azure_speech_key, config.azure_speech_region)
        app.state.text_to_voice=TextToVoice(config.azure_speech_key, config.azure_speech_region)
        logger.info("✅ TextToVoice service initialized.")

        # Initialize GPTAgent Service
        logger.info("Initializing GPTAgent...")
        # app.state.gpt_agent = GPTAgent()
        services["gpt_agent"] = GPTAgent()
        
        logger.info("✅ GPTAgent initialized.")

        logger.info("--- All services have been initialized successfully. ---")

    except Exception as e:
        # If any service fails, this will log the critical error.
        logger.critical(f"FATAL ERROR during service initialization: {e}", exc_info=True)
    # --- END OF FIX ---

    yield
    
    logger.info("--- Application shutting down... ---")
    
    services.clear()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# 6. WEBSOCKET ENDPOINT
# ==============================================================================
@app.websocket("/ws/voice-live")
async def websocket_endpoint(websocket: WebSocket):
    session_id = await manager.connect(websocket)
    session = manager.get_session(session_id)
    processor = manager.get_processor(session_id)

    if not session or not processor:
        logger.error(f"Failed to initialize session/processor.", extra={"session_id": session_id})
        return

    try:
        if not session['greeting_sent']:
            greeting_msg = "Voice Assistant ready. High-quality real-time processing enabled."
            await send_audio_response(websocket, greeting_msg, "greeting", session)
            session['greeting_sent'] = True
        
        while True:
            if websocket.client_state.name == "DISCONNECTED":
                logger.info("Client already disconnected, breaking loop.", extra={"session_id": session_id})
                break
            message = await websocket.receive()
            if message.get("type") == "websocket.receive":
                if "text" in message:
                    try:
                        data = json.loads(message["text"])
                        message_type = data.get("type")
                        event = data.get("event")
                        
                        if message_type == "config":
                            # Handle configuration message from frontend
                            logger.info(f"Received configuration: timezone={data.get('timezone')}, voice={data.get('voice')}", extra={"session_id": session_id})
                            session['timezone'] = data.get('timezone', 'UTC')
                            session['voice'] = data.get('voice', 'en-IN-NeerjaNeural')
                            # Send confirmation back to frontend
                            await websocket.send_text(json.dumps({
                                "type": "config_received",
                                "message": f"Configuration updated: {session['timezone']}, {session['voice']}",
                                "session_id": session_id
                            }))
                        elif event == "start_recording":
                            logger.info("Event: 'start_recording'. Enabling recording.", extra={"session_id": session_id})
                            processor.reset()
                            session['is_recording'] = True
                            session['timezone'] = data.get('timezone', session.get('timezone', 'UTC'))
                        elif event == "stop_recording":
                            logger.info("Event: 'stop_recording'. Processing final audio.", extra={"session_id": session_id})
                            session['is_recording'] = False
                            if len(processor.get_complete_audio()) > 0:
                                await process_complete_audio(websocket, session)
                        elif message_type == "client_text":
                            # Frontend sent a direct text command (e.g., option selection)
                            user_input = data.get("text", "")
                            logger.info(f"Received client_text: '{user_input}'", extra={"session_id": session_id})
                            if not user_input:
                                return
                            session['had_user_speech'] = True
                            if session.get('awaiting_conflict_resolution'):
                                await handle_conflict_resolution_response(websocket, user_input, session)
                            else:
                                intent, entities = await process_with_gpt(user_input, session)
                                if intent == "schedule_meeting":
                                    entities['timezone'] = session.get('timezone', 'UTC')
                                    await process_meeting_scheduling(websocket, entities, session)
                                else:
                                    reply = entities.get("reply", "I can only help schedule meetings.")
                                    await send_audio_response(websocket, reply, "clarification", session)
                    except Exception as e:
                        logger.error(f"Error handling control message: {e}", extra={"session_id": session_id}, exc_info=True)
                elif "bytes" in message:
                    if session.get('is_recording', False):
                        if processor.add_audio_chunk(message["bytes"]):
                            await process_complete_audio(websocket, session)
    except WebSocketDisconnect:
        logger.info("Client disconnected.", extra={"session_id": session_id})
    except Exception as e:
        logger.error(f"Unexpected WebSocket error: {e}", extra={"session_id": session_id}, exc_info=True)
    finally:
        manager.disconnect(session_id)

# ==============================================================================
# 7. CORE PROCESSING LOGIC
# ==============================================================================
async def process_complete_audio(websocket: WebSocket, session: dict):
    session_id = session['id']
    async with session['processing_lock']:
        processor = manager.get_processor(session_id)
        if not processor: return

        complete_audio = processor.get_complete_audio()
        audio_duration = len(complete_audio) / (SAMPLE_RATE * BYTES_PER_SAMPLE)
        logger.info(f"Processing audio segment of {audio_duration:.2f}s", extra={"session_id": session_id})

        # Allow very short replies (e.g., "option 1") during conflict selection
        if audio_duration < 0.5 and not session.get('awaiting_conflict_resolution'):
            # If no meaningful speech has occurred since the start, send a one-time helpful prompt without audio
            if not session.get('had_user_speech') and not session.get('greeting_sent'):
                await send_audio_response(
                    websocket,
                    "I can help you manage your meeting. For example, say 'Schedule a meeting tomorrow at 10 AM'.",
                    "prompt",
                    session,
                    {"mute_audio": True}
                )
                session['greeting_sent'] = True
            # Otherwise, remain silent on very short audio
            return

        temp_file = None
        try:
            await websocket.send_json({"type": "processing_started", "message": "🔄 Processing...", "session_id": session_id})
            temp_file = save_pcm_as_wav(bytearray(complete_audio))
            if not temp_file: raise Exception("Failed to save audio to WAV file.")

            user_input = await enhanced_speech_to_text(temp_file)
            logger.info(f"Raw transcription result: '{user_input}' (type: {type(user_input)})", extra={"session_id": session_id})
            
            await websocket.send_json({"type": "transcription", "text": user_input or "", "session_id": session_id})

            if not user_input or user_input.strip() == "":
                logger.warning(f"Empty transcription received for session {session_id}", extra={"session_id": session_id})
                # If awaiting a conflict selection, prompt the user instead of staying silent
                if session.get('awaiting_conflict_resolution'):
                    await send_audio_response(
                        websocket,
                        "I didn't catch that. Please say 'option 1', 'option 2', or 'option 3'.",
                        "clarification",
                        session,
                        {"mute_audio": True, "retry_conflict_resolution": True, "conflict_data": session.get('conflict_data')}
                    )
                    return
                # If this is the first interaction and it's silence, show a one-time prompt without TTS
                if not session.get('had_user_speech') and not session.get('greeting_sent'):
                    await send_audio_response(
                        websocket,
                        "I can help you manage your meeting. For example, say 'Schedule a meeting tomorrow at 10 AM'.",
                        "prompt",
                        session,
                        {"mute_audio": True}
                    )
                    session['greeting_sent'] = True
                # Otherwise, do not reply on silence
                return
            
            logger.info(f"Transcription: '{user_input}'", extra={"session_id": session_id})
            session['had_user_speech'] = True  # Mark that we have received meaningful speech
            
            # Check if we're awaiting conflict resolution
            if session.get('awaiting_conflict_resolution'):
                await handle_conflict_resolution_response(websocket, user_input, session)
                return
            
            intent, entities = await process_with_gpt(user_input, session)
            
            if intent == "schedule_meeting":
                entities['timezone'] = session.get('timezone', 'UTC')
                await process_meeting_scheduling(websocket, entities, session)
            else:
                reply = entities.get("reply", "I can only help schedule meetings.")
                # Do not speak the clarification if we are in conflict selection context
                await send_audio_response(websocket, reply, "clarification", session, {"mute_audio": session.get('awaiting_conflict_resolution', False)})
        except Exception as e:
            logger.error(f"CRITICAL ERROR in pipeline: {e}", extra={"session_id": session_id}, exc_info=True)
            await send_audio_response(websocket, "I ran into a problem processing that.", "error", session)
        finally:
            if temp_file: cleanup_temp_file(temp_file)
            logger.info("Finished processing audio segment.", extra={"session_id": session_id})

# In main.py
async def process_with_gpt(user_input: str, session: dict) -> tuple:
    import time
    try:
        # Combine new input with any partial details from the ongoing conversation
        partial_details = session.get('partial_meeting_details', {})
        
        context = {
            'timezone': session.get('timezone', 'UTC'),
            'session_duration': time.time() - session.get('start_time', 0),
            'previous_interactions': session.get('interaction_history', []),
            'partial_meeting_details': partial_details # Give the AI context
        }
        
        gpt_agent = services.get("gpt_agent")
        if not gpt_agent: raise Exception("GPTAgent service not found.")
        
        intent, new_entities = gpt_agent.process_input(user_input, context)
        
        # Combine old and new entities
        final_entities = {**partial_details, **new_entities}
        
        session['interaction_history'].append({'input': user_input, 'intent': intent})
        
        # Return the combined result
        return intent, final_entities
        
    except Exception as e:
        logger.error(f"💥 GPT processing error: {e}", exc_info=True)
        raise e

async def process_meeting_scheduling(websocket: WebSocket, entities: dict, session: dict):
        session_id = session.get('id', 'unknown')
        try:
            logger.info("Attempting to schedule meeting with entities.", extra={"session_id": session_id})
            
            text_to_voice =  _get_state_service(websocket, "text_to_voice") 
            calendar_service = services.get("calendar")
            if not text_to_voice or not calendar_service:
                raise Exception("A required service (TTS or Calendar) is not available.")
    
            # This function will now handle the conversation flow correctly.
            completed_entities = await fill_missing_fields_async(entities, text_to_voice, websocket, session)
            
            # If fill_missing_fields_async returned None, it means it asked a question and is waiting.
            # So we stop here and wait for the user's next input.
            if not completed_entities:
                logger.info("Awaiting more information from the user.", extra={"session_id": session_id})
                return
    
            # If we have all the details, proceed to schedule.
            logger.info(f"All details gathered. Scheduling event: {completed_entities}", extra={"session_id": session_id})
            result = calendar_service.intelligent_schedule_handler(completed_entities)
            
            if result.get('status') == 'scheduled':
                # Successfully scheduled
                meeting_details = result.get('event_details', {})
                meeting_title = meeting_details.get('summary') or completed_entities.get('title', 'your meeting')
                start_time = result.get('start_formatted', result.get('start', ''))
                response_text = f"Perfect! I've successfully scheduled '{meeting_title}' for {start_time}."
                
                await send_audio_response(websocket, response_text, "meeting_scheduled", session, {
                    "event_details": meeting_details,
                    "result": result
                })
                
            elif result.get('status') == 'conflict':
                # Handle scheduling conflict with multiple suggestions
                from core.conversation_flow import handle_conflict_resolution
                await handle_conflict_resolution(websocket, result, session)
                
            else:
                # Other errors
                response_text = f"I couldn't schedule the meeting: {result.get('message')}."
                await send_audio_response(websocket, response_text, "meeting_error", session)
    
        except Exception as e:
            logger.error(f"💥 Meeting scheduling error: {e}", extra={"session_id": session_id}, exc_info=True)
            await send_audio_response(websocket, "Sorry, I ran into an error while trying to schedule the meeting.", "error", session)

async def handle_conflict_resolution_response(websocket: WebSocket, user_input: str, session: dict):
    """
    Handles the user's response to conflict resolution options.
    """
    session_id = session.get('id', 'unknown')
    
    try:
        from core.conversation_flow import process_conflict_selection
        
        # Process the user's selection
        selection = await process_conflict_selection(user_input, session)
        
        if selection is None:
            # Invalid selection, provide more detailed guidance with improved error handling
            # Count the number of retry attempts
            retry_count = session.get('conflict_resolution_retry_count', 0)
            session['conflict_resolution_retry_count'] = retry_count + 1
            
            # Customize message based on retry count
            if retry_count >= 2:
                # After multiple failures, provide more explicit guidance
                message = "I'm still having trouble understanding your selection. Please try one of these exact phrases: 'option 1', 'option 2', 'option 3', 'one', 'two', 'three', or 'different times'. You can also try speaking more slowly and clearly."
            else:
                # Standard guidance for first few attempts
                message = "I couldn't understand your selection. Please clearly say 'option 1', 'option 2', 'option 3', or you can say 'different times' if none of these work for you. You can also say just the number like 'one', 'two', or 'three'."
            
            await send_audio_response(
                websocket, 
                message,
                "clarification",
                session,
                {
                    "retry_conflict_resolution": True,
                    "conflict_data": session.get('conflict_data'),
                    "mute_audio": False  # Play the audio guidance to help user
                }
            )
            return
        
        if selection == 'different':
            # User wants different options
            session.pop('awaiting_conflict_resolution', None)
            session.pop('conflict_data', None)
            # Also clear the retry counter
            session.pop('conflict_resolution_retry_count', None)
            await send_audio_response(
                websocket,
                "I understand you'd like different time options. Let me know what specific time you'd prefer, or I can suggest times for a different day.",
                "clarification",
                session,
                {"mute_audio": False}  # Play audio to confirm the selection
            )
            return
        
        # User selected a valid option (1, 2, or 3)
        # Reset the retry counter since we got a valid selection
        session.pop('conflict_resolution_retry_count', None)
        
        conflict_data = session.get('conflict_data')
        if not conflict_data:
            await send_audio_response(
                websocket,
                "I'm sorry, I lost track of the scheduling options. Let's start over with scheduling your meeting.",
                "error",
                session
            )
            session.pop('awaiting_conflict_resolution', None)
            return
        
        # Get the original meeting data from the conflict (preserved from the original request)
        original_meeting_data = session.get('original_meeting_data')
        if not original_meeting_data:
            # Fallback to partial meeting details if original data is missing
            original_meeting_data = {
                'title': session.get('partial_meeting_details', {}).get('title'),
                'date': session.get('partial_meeting_details', {}).get('date'),
                'time': session.get('partial_meeting_details', {}).get('time'),
                'timezone': conflict_data.get('timezone', 'UTC'),
                'attendees': session.get('partial_meeting_details', {}).get('attendees', [])
            }
        
        # Schedule using the selected option
        calendar_service = services.get("calendar")
        if not calendar_service:
            raise Exception("Calendar service not available")
        
        result = calendar_service.schedule_suggested_slot(original_meeting_data, selection)
        
        # Clear conflict resolution state
        session.pop('awaiting_conflict_resolution', None)
        session.pop('conflict_data', None)
        session.pop('original_meeting_data', None)
        session.pop('partial_meeting_details', None)
        session.pop('conflict_resolution_retry_count', None)  # Clear retry counter
        
        if result.get('status') == 'scheduled':
            meeting_title = result.get('event_details', {}).get('summary', 'your meeting')
            start_time = result.get('start_formatted', '')
            response_text = f"Excellent! I've scheduled '{meeting_title}' for {start_time} (Option {selection} - {result.get('description', '')})."
            
            await send_audio_response(websocket, response_text, "meeting_scheduled", session, {
                "event_details": result.get('event_details', {}),
                "result": result
            })
        else:
            error_message = result.get('message', 'Unknown error occurred')
            await send_audio_response(
                websocket,
                f"I'm sorry, I couldn't schedule that option: {error_message}. Would you like to try a different time?",
                "meeting_error",
                session
            )
        
    except Exception as e:
        logger.error(f"Error handling conflict resolution response: {e}", extra={"session_id": session_id}, exc_info=True)
        session.pop('awaiting_conflict_resolution', None)
        session.pop('conflict_data', None)
        await send_audio_response(
            websocket,
            "I encountered an error processing your selection. Let's start over with scheduling your meeting.",
            "error",
            session
        )

# ==============================================================================
# 8. HTTP ENDPOINTS
# ==============================================================================
@app.get("/", tags=["root"])
async def read_root():
    return {"message": "🎤 Voice-based Meeting Scheduler API v3.0"}

@app.get("/calendar/availability-test")
async def test_availability(start: str, end: str, timezone: str):
    # calendar_service =  _get_state_service(websocket, "calendar") or services.get("calendar")
    calendar_service = services.get("calendar")
    if not calendar_service:
        raise HTTPException(status_code=500, detail="Calendar service not loaded")
    try:
        availability = calendar_service.get_availability(start, end, timezone)
        logger.info(f"Successfully retrieved {len(availability)} events.")
        return {"availability":availability}
    except Exception as e:
        logger.error(f"Error fetching availability: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching availability.")

# ==============================================================================
# 9. HELPER FUNCTIONS
# ==============================================================================
def _get_state_service(websocket: WebSocket, name: str):
    try:
        return getattr(websocket.app.state, name, None)
    except Exception:
        return None

def save_pcm_as_wav(audio_buffer: bytearray) -> Optional[str]:
    try:
        temp_fd, temp_path = tempfile.mkstemp(suffix='.wav')
        with os.fdopen(temp_fd, 'wb') as f:
            with wave.open(f, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(BYTES_PER_SAMPLE)
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.writeframes(audio_buffer)
        return temp_path
    except Exception as e:
        logger.error(f"💥 Error saving PCM as WAV: {e}", exc_info=True)
        return None

def cleanup_temp_file(file_path: str):
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
    except Exception as e:
        logger.warning(f"⚠️ Failed to cleanup temp file {file_path}: {e}")

async def send_audio_response(websocket: WebSocket, text: str, response_type: str, session: dict, extra_data: dict = None):
    session_id = session.get('id', 'unknown')
    
    # Check if WebSocket is still connected
    try:
        if websocket.client_state.name == "DISCONNECTED":
            logger.warning("WebSocket disconnected, cannot send response.", extra={"session_id": session_id})
            return
    except AttributeError:
        logger.warning("Cannot check WebSocket state.", extra={"session_id": session_id})
    
    try:
        response_data = {
            "type": response_type,
            "message": text,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        if extra_data:
            response_data.update(extra_data)
        
        # Allow callers to mute TTS audio by passing {'mute_audio': True}
        mute_audio = bool(extra_data.get('mute_audio')) if isinstance(extra_data, dict) else False
        
        text_to_voice =  _get_state_service(websocket, "text_to_voice") 
        if text_to_voice and not mute_audio:
            logger.info(f"🗣️ Synthesizing: {text}", extra={"session_id": session_id})
            try:
                audio_response = text_to_voice.synthesize(text)
                if audio_response and len(audio_response) > 0:
                    logger.info(f"🔊 Synthesis successful: {len(audio_response)} bytes", extra={"session_id": session_id})
                    response_data["audio"] = audio_response.hex()
                else:
                    logger.warning("Audio synthesis returned empty.", extra={"session_id": session_id})
            except Exception as e:
                logger.error(f"Audio synthesis failed: {e}", extra={"session_id": session_id})
        elif not text_to_voice:
            logger.warning("TextToVoice service not found. Sending response without audio.", extra={"session_id": session_id})
        else:
            logger.info("Audio muted for this response.", extra={"session_id": session_id})
            
        await websocket.send_json(response_data)
        logger.info(f"🗣️ Sent response [{response_type}] to client.", extra={"session_id": session_id})
        
    except WebSocketDisconnect:
        logger.warning(f"Client disconnected before response could be sent.", extra={"session_id": session_id})
    except Exception as e:
        logger.error(f"💥 Error in send_audio_response: {e}", extra={"session_id": session_id}, exc_info=True)


# ==============================================================================
# 10. SERVER RUN
# ==============================================================================
if __name__ == "__main__":
    import uvicorn    
    uvicorn.run(app, host="localhost", port=8000)