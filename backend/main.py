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
        logger.info("ConnectionManager initialized.")

    async def connect(self, websocket: WebSocket) -> int:
        await websocket.accept()
        session_id = id(websocket)
        self.audio_processors[session_id] = SmartAudioProcessor()
        self.active_sessions[session_id] = {
            'id': session_id,
            'websocket': websocket,
            'timezone': 'UTC',
            'is_recording': False,
            'processing_lock': asyncio.Lock(),
            'greeting_sent': False,
            'start_time': time.time(),
            'interaction_history': []
        }
        logger.info("New connection established", extra={"session_id": session_id})
        return session_id

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
    logger.info("Application starting up...")
    config = Config()
    services["calendar"] = CalendarService()
    services["text_to_voice"] = TextToVoice(config.azure_speech_key, config.azure_speech_region)
    services["gpt_agent"] = GPTAgent()
    logger.info("All services have been initialized successfully.")
    yield
    logger.info("Application shutting down...")
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
            message = await websocket.receive()
            if message.get("type") == "websocket.receive":
                if "text" in message:
                    try:
                        data = json.loads(message["text"])
                        event = data.get("event")
                        if event == "start_recording":
                            logger.info("Event: 'start_recording'. Enabling recording.", extra={"session_id": session_id})
                            processor.reset()
                            session['is_recording'] = True
                            session['timezone'] = data.get('timezone', 'UTC')
                        elif event == "stop_recording":
                            logger.info("Event: 'stop_recording'. Processing final audio.", extra={"session_id": session_id})
                            session['is_recording'] = False
                            if len(processor.get_complete_audio()) > 0:
                                await process_complete_audio(websocket, session)
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

        if audio_duration < 0.5:
            await send_audio_response(websocket, "I didn't hear enough audio, please try again.", "insufficient_audio", session)
            return

        temp_file = None
        try:
            await websocket.send_json({"type": "processing_started", "message": "🔄 Processing...", "session_id": session_id})
            temp_file = save_pcm_as_wav(bytearray(complete_audio))
            if not temp_file: raise Exception("Failed to save audio to WAV file.")

            user_input = await enhanced_speech_to_text(temp_file)
            await websocket.send_json({"type": "transcription", "text": user_input or "", "session_id": session_id})

            if not user_input:
                await send_audio_response(websocket, "I couldn't quite understand that.", "unclear_speech", session)
                return
            
            logger.info(f"Transcription: '{user_input}'", extra={"session_id": session_id})
            
            intent, entities = await process_with_gpt(user_input, session)
            
            if intent == "schedule_meeting":
                entities['timezone'] = session.get('timezone', 'UTC')
                await process_meeting_scheduling(websocket, entities, session)
            else:
                reply = entities.get("reply", "I can only help schedule meetings.")
                await send_audio_response(websocket, reply, "clarification", session)
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
        
        session.get('interaction_history', []).append({'input': user_input, 'intent': intent})
        
        # Return the combined result
        return intent, final_entities
        
    except Exception as e:
        logger.error(f"💥 GPT processing error: {e}", exc_info=True)
        raise e

async def process_meeting_scheduling(websocket: WebSocket, entities: dict, session: dict):
    try:
        text_to_voice = services.get("text_to_voice")
        calendar_service = services.get("calendar")
        
        completed_entities = await fill_missing_fields_async(entities, text_to_voice, websocket, session)
        if not completed_entities: return # Conversation is ongoing
        
        result = calendar_service.intelligent_schedule_handler(completed_entities)
        
        if result.get('status') == 'success' or result.get('status') == 'scheduled':
            response_text = f"Perfect! I've successfully scheduled '{result.get('title')}' for {result.get('start')}."
        else:
            response_text = f"I couldn't schedule the meeting: {result.get('message')}."
        
        await send_audio_response(websocket, response_text, "meeting_result", session, {"event_details": result})
    except Exception as e:
        logger.error(f"💥 Meeting scheduling error: {e}", exc_info=True)
        await send_audio_response(websocket, f"Sorry, scheduling failed.", "error", session)

# ==============================================================================
# 8. HTTP ENDPOINTS
# ==============================================================================
@app.get("/", tags=["root"])
async def read_root():
    return {"message": "🎤 Voice-based Meeting Scheduler API v3.0"}

@app.get("/calendar/availability-test")
async def test_availability(start: str, end: str, timezone: str):
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
    try:
        response_data = {
            "type": response_type, "message": text, "session_id": session['id']
        }
        if extra_data: response_data.update(extra_data)
        
        text_to_voice = services.get("text_to_voice")
        audio_response = text_to_voice.synthesize(text)
        if audio_response:
            response_data["audio"] = audio_response.hex()
        
        await websocket.send_json(response_data)
    except Exception as e:
        logger.error(f"💥 Error sending response to {session['id']}: {e}", exc_info=True)

# ==============================================================================
# 10. SERVER RUN
# ==============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)