
import tempfile
import azure.cognitiveservices.speech as speechsdk
import traceback
from fastapi import FastAPI, File, UploadFile, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio
from typing import Dict, Any, Optional
import logging
import json
from datetime import datetime
import pytz
import numpy as np
from pydub import AudioSegment
import time
import wave
import io
import struct
from fastapi.responses import HTMLResponse
# Import your core modules
from core.smart_audio_processor import SmartAudioProcessor
from core.calendar_service import CalendarService
from core.voice_to_text import VoiceToText
from core.text_to_voice import TextToVoice
from core.run_gpt_agent import GPTAgent
from core.validation import validate_meeting_details
from core.conversation_flow import fill_missing_fields, handle_scheduling
from core.timezone_utils import parse_datetime, validate_timezone
from config.config import Config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')  # Missing closing parenthesis
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS configuration
origins = ["http://localhost:3000", "http://localhost:3001", "https://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
# ADD THESE MISSING LINES:
processing_lock = {}
active_sessions = {}

config = Config()
calendar_service = CalendarService()
voice_to_text = VoiceToText(config.azure_speech_key, config.azure_speech_region)
text_to_voice = TextToVoice(config.azure_speech_key, config.azure_speech_region)
gpt_agent = GPTAgent(config.gpt_api_key)
# Add these lines after line 39 (after gpt_agent = GPTAgent...)
audio_processors: Dict[int, SmartAudioProcessor] = {}
processing_status: Dict[int, bool] = {}



time=datetime.now()  # Initialize current time for logging
# Exit commands

EXIT_COMMANDS = ["stop", "exit", "quit", "bye", "goodbye", "that's it", "cancel", "okay"]

# Audio processing constants
SAMPLE_RATE = 16000
CHANNELS = 1
BYTES_PER_SAMPLE = 2
CHUNK_SIZE = 1024  # Optimal chunk size for real-time processing
SILENCE_THRESHOLD = 300  # Amplitude threshold for silence detection
SILENCE_DURATION = 1.5  # Seconds of silence before auto-processing

@app.get("/", tags=["root"])
async def read_root():
    return {"message": "🎤 Voice-based Meeting Scheduler API v2.0"}
async def handle_audio_data(websocket: WebSocket, session_id: int, audio_data: bytes):
    """Handle incoming audio with smart processing"""
    
    if processing_status.get(session_id, False):
        print("⚠️ Already processing, skipping chunk")
        return
    
    processor = audio_processors.get(session_id)
    if not processor:
        return
    
    # Check if ready to process complete sentence
    should_process = processor.add_audio_chunk(audio_data)
    
    if should_process:
        processing_status[session_id] = True
        
        try:
            # Get complete audio
            complete_audio = processor.get_complete_audio()
            
            # Send processing message
            await websocket.send_json({
                "type": "processing_started",
                "message": "🔄 Processing complete sentence...",
                "audio_duration": len(complete_audio) / (16000 * 2)
            })
            
            # Process with your existing logic
            await process_complete_audio(websocket, session_id, complete_audio)
            
        except Exception as e:
            print(f"❌ Processing error: {e}")
            await websocket.send_json({
                "type": "processing_error",
                "message": f"Processing failed: {e}"
            })
        finally:
            processing_status[session_id] = False


async def handle_audio_data_smart(websocket: WebSocket, session_id: int, audio_data: bytes):
    """Handle audio data with smart processing logic"""
    
    if processing_status.get(session_id, False):
        logger.warning("⚠️ Already processing, skipping chunk")
        return
    
    processor = audio_processors.get(session_id)
    session = active_sessions.get(session_id)
    
    if not processor or not session:
        return
    
    # Use SmartAudioProcessor to determine if ready to process
    should_process = processor.add_audio_chunk(audio_data)
    
    # IMPORTANT: Update session buffer with SmartAudioProcessor's buffer
    if should_process:
        processing_status[session_id] = True
        
        try:
            # Get complete audio from SmartAudioProcessor
            complete_audio = processor.get_complete_audio()
            
            # FIXED: Update session buffer with complete audio
            session['audio_buffer'] = bytearray(complete_audio)
            session['total_audio_duration'] = len(complete_audio) / (16000 * 2)
            
            # Send processing message
            await websocket.send_json({
                "type": "processing_started",
                "message": "🔄 Processing complete sentence...",
                "audio_duration": len(complete_audio) / (16000 * 2)
            })
            
            # Process with existing logic
            await process_complete_audio(websocket, session)
            
        except Exception as e:
            logger.error(f"❌ Smart processing error: {e}")
            await websocket.send_json({
                "type": "processing_error",
                "message": f"Processing failed: {e}"
            })
        finally:
            processing_status[session_id] = False


async def handle_control_message_new(websocket: WebSocket, message: dict, session: dict, websocket_id: int):
    """Handle control messages with smart processor integration"""
    try:
        event = message.get("event")
        
        if event == "start_recording":
            # Reset both processors using the numeric ID
            if websocket_id in audio_processors:
                audio_processors[websocket_id].reset()
            
            session['is_recording'] = True
            session['audio_buffer'].clear()
            session['timezone'] = message.get('timezone', 'UTC')
            
            await websocket.send_json({
                "type": "recording_started",
                "message": "🔴 Recording started - speak now!"
            })
        
        elif event == "stop_recording":
            session['is_recording'] = False
            
            # Use the numeric ID for audio_processors
            processor = audio_processors.get(websocket_id)
            if processor and len(processor.audio_buffer) > 0:
                complete_audio = processor.get_complete_audio()
                session['audio_buffer'] = bytearray(complete_audio)
                await process_complete_audio(websocket, session)
            
            await websocket.send_json({
                "type": "recording_stopped",
                "message": "⏹️ Recording stopped"
            })
        
        elif event == "ping":
            await websocket.send_json({
                "type": "pong",
                "session_id": session['id']
            })
            
    except Exception as e:
        logger.error(f"❌ Error in handle_control_message_new: {e}")
        import traceback
        logger.error(traceback.format_exc())


@app.websocket("/ws/voice-live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = id(websocket)
    
    # Initialize processor for this session
    audio_processors[session_id] = SmartAudioProcessor()
    processing_status[session_id] = False
    
    # Initialize session
    session = {
        'id': str(session_id),
        'audio_buffer': bytearray(),
        'timezone': 'UTC',
        'is_recording': False,
        'silence_timer': None,
        'processing': False,
        'temp_files': [],
        'last_activity': time.time(),
        'total_audio_duration': 0,
        'chunk_count': 0,
        'audio_quality_samples': [],
        'greeting_sent': False  # ADD THIS FLAG
    }
    
    active_sessions[session_id] = session
    
    try:
        # Send greeting
        if not session['greeting_sent']:
            greeting_msg = "Voice Assistant ready! High-quality real-time processing enabled."
            await send_audio_response(websocket, greeting_msg, "greeting", session)
            session['greeting_sent'] = True
        
        while True:
            try:
                message = await websocket.receive()
                # Add this debug logging in your WebSocket loop before processing:
                # logger.info(f"🔍 DEBUG - Message received: {message}")
                # logger.info(f"🔍 DEBUG - Message type: {type(message)}")
                # if "text" in message:
                #      logger.info(f"🔍 DEBUG - Text content: {message['text']}")
                #      logger.info(f"🔍 DEBUG - Text type: {type(message['text'])}")

                # FIXED: Better message type checking
                if message.get("type") == "websocket.receive":
                    if "text" in message:
                        # Handle control messages
                        try:
                            text_data = message["text"]
                            if isinstance(text_data, str):  # Ensure it's a string
                                data = json.loads(text_data)
                                logger.info(f"📨 Control event [{session_id}]: {data.get('event')}")
                                await handle_control_message_new(websocket, data, session, session_id)
                            else:
                                logger.error(f"❌ Invalid text data type: {type(text_data)}")
                        except json.JSONDecodeError as e:
                            logger.error(f"❌ Invalid JSON received: {e}")
                        except Exception as e:
                            logger.error(f"❌ Error processing text message: {e}")
                            
                    elif "bytes" in message:
                        # Handle audio data with SMART processing
                        await handle_audio_data_smart(websocket, session_id, message["bytes"])
                        
            except Exception as e:
                   # Check if it's a disconnect error
                if "disconnect" in str(e).lower() or "receive" in str(e).lower():
                    logger.info(f"🔌 WebSocket {session_id} disconnected: {e}")
                    break
                else:
                    logger.error(f"❌ Error in WebSocket loop: {e}")
                
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket {session_id} disconnected")
    finally:
        # Cleanup
        audio_processors.pop(session_id, None)
        processing_status.pop(session_id, None)
        active_sessions.pop(session_id, None)
        if session_id in audio_processors:
            audio_processors.pop(session_id, None)
        if session_id in processing_status:
            processing_status.pop(session_id, None)
        if session_id in active_sessions:
            active_sessions.pop(session_id, None)

async def handle_control_message(websocket: WebSocket, message: dict, session: dict):
    """Enhanced control message handler with better error handling"""
    try:
        event = message.get("event")
        session['last_activity'] = time.time()
        
        logger.info(f"📨 Control event [{session['id']}]: {event}")
        
        if event == "start_recording":
            logger.info(f"▶️ Start recording requested for {session['id']}")
            session['timezone'] = message.get('timezone', 'UTC')
            session['is_recording'] = True
            session['audio_buffer'].clear()
            session['chunk_count'] = 0
            session['total_audio_duration'] = 0
            session['audio_quality_samples'].clear()
            
            logger.info(f"▶️ Recording started for {session['id']} with timezone: {session['timezone']}")
            
            await websocket.send_json({
                "type": "recording_started",
                "message": "🔴 Recording started - speak now!",
                "session_id": session['id'],
                "timestamp": datetime.now().isoformat()
            })
            
        elif event == "stop_recording":
            session['is_recording'] = False
            logger.info(f"⏹️ Stop recording requested for {session['id']}")
            
            if len(session['audio_buffer']) > 0 and not session['processing']:
                await process_complete_audio(websocket, session)
            else:
                await websocket.send_json({
                    "type": "recording_stopped",
                    "message": "Recording stopped - no audio to process",
                    "session_id": session['id']
                })
            
        elif event == "cancel_recording":
            await cancel_recording(websocket, session)
            
        elif event == "ping":
            await websocket.send_json({
                "type": "pong",
                "session_id": session['id'],
                "timestamp": datetime.now().isoformat()
            })
            
    except Exception as e:
        logger.error(f"💥 Error handling control message for {session['id']}: {e}")
        await send_error_response(websocket, f"Control error: {str(e)}")

async def handle_audio_chunk(websocket: WebSocket, audio_data: bytes, session: dict):
    """Enhanced audio chunk handler with quality monitoring"""
    try:
        # if not session['is_recording'] or session['processing']:
        #      logger.warning(f"🚫 Skipping chunk - Recording: {session['is_recording']}, Processing: {session['processing']}")
        #      return
        
        session['last_activity'] = time.time()
        session['chunk_count'] += 1
        
        # Add to buffer
        buffer_before = len(session['audio_buffer'])
        session['audio_buffer'].extend(audio_data)
        buffer_after = len(session['audio_buffer'])
        
        logger.info(f"📊 Chunk {session['chunk_count']}: Buffer {buffer_before} → {buffer_after} bytes (+{len(audio_data)})")
        
        # Calculate audio quality metrics
        quality_metrics = analyze_audio_quality(audio_data)
        session['audio_quality_samples'].append(quality_metrics)
        
        # Estimate audio duration (assuming 16kHz, 16-bit, mono)
        duration_increment = len(audio_data) / (SAMPLE_RATE * BYTES_PER_SAMPLE)
        session['total_audio_duration'] += duration_increment
        
        logger.debug(f"🎵 Chunk {session['chunk_count']}: {len(audio_data)} bytes, "
                    f"Quality: {quality_metrics['rms']:.0f}, "
                    f"Total duration: {session['total_audio_duration']:.2f}s")
        
        # Advanced silence detection
        is_silent = quality_metrics['rms'] < SILENCE_THRESHOLD
        
        if is_silent:
            if session['silence_timer'] is None and session['total_audio_duration'] > 0.5:
                session['silence_timer'] = asyncio.create_task(
                    silence_timeout(websocket, session, SILENCE_DURATION)
                )
        else:
            # Cancel silence timer if we detect audio
            if session['silence_timer']:
                session['silence_timer'].cancel()
                session['silence_timer'] = None
        
        # Send real-time feedback
        if session['chunk_count'] % 10 == 0:  # Every 10th chunk
            avg_quality = np.mean([s['rms'] for s in session['audio_quality_samples'][-10:]])
            await websocket.send_json({
                "type": "audio_feedback",
                "chunk_count": session['chunk_count'],
                "total_bytes": len(session['audio_buffer']),
                "duration": round(session['total_audio_duration'], 2),
                "quality": round(avg_quality, 0),
                "is_silent": is_silent
            })
        
    except Exception as e:
        logger.error(f"💥 Error handling audio chunk for {session['id']}: {e}")

def analyze_audio_quality(audio_data: bytes) -> dict:
    """Analyze audio quality metrics"""
    try:
        if len(audio_data) < 2:
            return {'rms': 0, 'peak': 0, 'snr_estimate': 0}
            
        # Convert bytes to int16 samples
        samples = np.frombuffer(audio_data, dtype=np.int16)
        
        # Calculate RMS (Root Mean Square)
        rms = np.sqrt(np.mean(samples.astype(np.float32)**2))
        
        # Peak amplitude
        peak = np.max(np.abs(samples))
        
        # Simple SNR estimate (signal-to-noise ratio)
        if rms > 0:
            snr_estimate = 20 * np.log10(peak / max(rms, 1))
        else:
            snr_estimate = 0
        
        return {
            'rms': float(rms),
            'peak': float(peak),
            'snr_estimate': float(snr_estimate)
        }
        
    except Exception as e:
        logger.warning(f"⚠️ Audio quality analysis failed: {e}")
        return {'rms': 0, 'peak': 0, 'snr_estimate': 0}

async def silence_timeout(websocket: WebSocket, session: dict, delay: float):
    """Enhanced silence timeout with progressive delay"""
    try:
        await asyncio.sleep(delay)
        
        if len(session['audio_buffer']) > 0 and not session['processing']:
            logger.info(f"🔇 Silence timeout triggered for {session['id']}, processing audio...")
            await process_complete_audio(websocket, session)
            
    except asyncio.CancelledError:
        logger.debug(f"🔇 Silence timer cancelled for {session['id']}")
    except Exception as e:
        logger.error(f"💥 Error in silence timeout for {session['id']}: {e}")

async def process_complete_audio(websocket: WebSocket, session: dict):
    """Enhanced audio processing with better error handling and optimization"""
    session_id = session['id']
        
    # Log buffer state
    buffer_size = len(session['audio_buffer'])
    logger.info(f"🔄 Starting audio processing for {session_id}:")
    logger.info(f"   📊 Buffer size: {buffer_size} bytes")
    logger.info(f"   📊 Chunk count: {session['chunk_count']}")
    logger.info(f"   📊 Duration: {session['total_audio_duration']:.2f}s")
    logger.info(f"   📊 Recording: {session['is_recording']}")
    logger.info(f"   📊 Processing: {session['processing']}")
    
    if buffer_size == 0:
        logger.error(f"❌ Audio buffer is EMPTY for session {session_id}!")
        await send_audio_response(websocket, 
            "No audio data received. Please try recording again.", 
            "no_audio", session)
        return
        
    # Prevent duplicate processing
    # if session_id in processing_lock or session['processing']:
    #     logger.warning(f"⚠️ Already processing session {session_id}, skipping")
    #     return
        
    # processing_lock[session_id] = True
    session['processing'] = True
    temp_file = None
    # Prevent duplicate processing
    # if session_id in processing_lock or session['processing']:
    #     logger.warning(f"⚠️ Already processing session {session_id}, skipping")
    #     return
        
    # # processing_lock[session_id] = True
    # session['processing'] = True
    # temp_file = None
    
    try:
        await websocket.send_json({
            "type": "processing_started",
            "message": "🔄 Processing your speech...",
            "audio_duration": round(session['total_audio_duration'], 2),
            "audio_size": len(session['audio_buffer']),
            "session_id": session_id
        })
        logger.info(f"🔄 Processing audio for session {session_id} ({len(session['audio_buffer'])} bytes)"  )
        # Validate audio buffer
        # if len(session['audio_buffer']) < SAMPLE_RATE:  # Less than 1 second
        #     await send_audio_response(websocket, 
        #         "I didn't receive enough audio. Please speak for at least 1 second.", 
        #         "insufficient_audio", session)
        #     return
        
        # Quality check
        # overall_quality = validate_audio_buffer_quality(session['audio_buffer'])
        # if not overall_quality['is_valid']:
        #     await send_audio_response(websocket, 
        #         f"Audio quality issue: {overall_quality['reason']}. Please try again.", 
        #         "poor_quality", session)
        #     return
        
        # Save audio as WAV file
        temp_file = await save_pcm_as_wav(session['audio_buffer'])
        if not temp_file:
            raise Exception("Failed to save audio file")
            
        session['temp_files'].append(temp_file)
        
        # Enhanced Speech-to-Text
        user_input = await enhanced_speech_to_text(temp_file, session)
        
        # if not user_input or len(user_input.strip()) < 2:
        #     await send_audio_response(websocket, 
        #         "I couldn't understand what you said. Please speak more clearly and try again.", 
        #         "unclear_speech", session)
        #     return
        if user_input and len(user_input.strip()) > 0:
            await websocket.send_json({
            "type": "transcription",
            "text": user_input,
            "confidence": "high",  # You could get this from Azure STT
            "session_id": session_id
        })
        else:
        # Send error if no transcription
            await websocket.send_json({
            "type": "transcription",
            "text": "No speech recognized",
            "confidence": "low", 
            "session_id": session_id
        })
            await send_audio_response(websocket, 
            "I couldn't understand what you said. Please try again.", 
            "unclear_speech", session)
        
        # Check for exit commands
        if any(cmd in user_input.lower() for cmd in EXIT_COMMANDS):
            await send_audio_response(websocket, 
                "Goodbye! Thanks for using the voice assistant.", 
                "goodbye", session)
            return
        
        # Enhanced GPT Processing
        try:
            intent, entities = await process_with_gpt(user_input, session)
        except Exception as e:
            logger.error(f"💥 GPT processing error for {session_id}: {e}")
            await send_audio_response(websocket, 
                "I had trouble understanding your request. Please try rephrasing it.", 
                "processing_error", session)
            return
        
        if intent != "schedule_meeting":
            response_text = entities.get("reply", 
                "I can help you schedule meetings. Please tell me about the meeting you'd like to schedule - "
                "include details like who you're meeting with, when, and for how long.")
            await send_audio_response(websocket, response_text, "clarification", session)
            return
        
        # Enhanced Meeting Scheduling
        entities['timezone'] = session['timezone']
        await process_meeting_scheduling(websocket, entities, session)
        
    except Exception as e:
        logger.error(f"💥 Processing error for {session_id}: {str(e)}")
        await send_audio_response(websocket, 
            "I encountered an error processing your request. Please try again.", 
            "error", session)
    finally:
        # Cleanup
        session['processing'] = False
        session['audio_buffer'].clear()
        session['chunk_count'] = 0
        session['total_audio_duration'] = 0
        
        if session['silence_timer']:
            session['silence_timer'].cancel()
            session['silence_timer'] = None
        
        if temp_file:
            # cleanup_temp_file(temp_file)
            pass
        
        if session_id in processing_lock:
            del processing_lock[session_id]
# ADD THIS FUNCTION:
async def process_meeting_scheduling(websocket: WebSocket, entities: dict, session: dict):
    """Process meeting scheduling with enhanced error handling"""
    try:
        logger.info(f"Processing meeting scheduling for session {session['id']}")
        
        # Enhanced field completion
        completed_entities = await fill_missing_fields_async(entities, text_to_voice, websocket, session)
        
        # Schedule the meeting
        result = calendar_service.intelligent_schedule_handler(completed_entities)
        
        if result.get('status') == 'success':
            meeting_details = result.get('event_details', {})
            response_text = (f"Perfect! I've successfully scheduled your meeting "
                           f"'{meeting_details.get('title', 'Meeting')}' "
                           f"for {meeting_details.get('start', 'the requested time')}.")
        else:
            error_msg = result.get('message', 'Unknown error occurred')
            response_text = f"I couldn't schedule the meeting: {error_msg}. Would you like to try with different details?"
        
        await send_audio_response(websocket, response_text, "meeting_result", session, {
            "status": result.get('status', 'error'),
            "event_details": result
        })
        
    except Exception as e:
        logger.error(f"💥 Meeting scheduling error for {session['id']}: {str(e)}")
        await send_audio_response(websocket, f"Sorry, scheduling failed: {str(e)}", "error", session)
# ADD THIS FUNCTION:
async def fill_missing_fields_async(entities: dict, text_to_voice, websocket: WebSocket, session: dict) -> dict:
    """Async wrapper for fill_missing_fields function"""
    try:
        # Import the function from conversation_flow
        from core.conversation_flow import fill_missing_fields
        
        # Check if fill_missing_fields is async
        if asyncio.iscoroutinefunction(fill_missing_fields):
            return await fill_missing_fields(entities, text_to_voice, websocket)
        else:
            # If it's sync, use thread executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: fill_missing_fields(entities, text_to_voice, websocket))
            
    except Exception as e:
        logger.error(f"Error in fill_missing_fields for {session['id']}: {e}")
        return entities

async def enhanced_speech_to_text(file_path: str, session: dict) -> str:
    """Enhanced STT with multiple language support and better error handling"""
    
    try:
        logger.info(f"🎙️ Enhanced STT processing for {session['id']}")
        
        if not os.path.exists(file_path):
            raise Exception(f"Audio file not found: {file_path}")
            
        file_size = os.path.getsize(file_path)
        logger.info(f"📊 Audio file size: {file_size} bytes")
        
        # Enhanced speech config
        speech_config = speechsdk.SpeechConfig(
            subscription=config.azure_speech_key,
            region=config.azure_speech_region
        )
        
        # Enable detailed results
        speech_config.enable_dictation()
        speech_config.request_word_level_timestamps()
        
        # Try multiple languages/models
        language_configs = [
            {"lang": "en-US", "model": "latest"},
            # {"lang": "en-GB", "model": "latest"},
            # {"lang": "en-AU", "model": "latest"}
        ]
        
        for config_item in language_configs:
            try:
                speech_config.speech_recognition_language = config_item["lang"]
                
                # Use continuous recognition for better accuracy
                audio_input = speechsdk.audio.AudioConfig(filename=file_path)
                speech_recognizer = speechsdk.SpeechRecognizer(
                    speech_config=speech_config, 
                    audio_config=audio_input
                )
                
                # Add event handlers for detailed feedback
                result = speech_recognizer.recognize_once()
                
                if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    if result.text and len(result.text.strip()) > 0:
                        confidence = getattr(result, 'confidence', 0.8)
                        logger.info(f"✅ STT Success ({config_item['lang']}): '{result.text}' (confidence: {confidence})")
                        return result.text.strip()
                        
                elif result.reason == speechsdk.ResultReason.NoMatch:
                    logger.warning(f"⚠️ No speech recognized with {config_item['lang']}")
                    
                elif result.reason == speechsdk.ResultReason.Canceled:
                    cancellation = result.cancellation_details
                    logger.warning(f"⚠️ STT Canceled ({config_item['lang']}): {cancellation.reason}")
                    
            except Exception as lang_error:
                logger.warning(f"⚠️ STT failed for {config_item['lang']}: {lang_error}")
                continue
        
        return ""
            
    except Exception as e:
        logger.error(f"💥 Enhanced STT error: {str(e)}")
        return ""

async def process_with_gpt(user_input: str, session: dict) -> tuple:
    """Enhanced GPT processing with context awareness"""
    try:
        # Add session context for better understanding
        context = {
            'timezone': session.get('timezone', 'UTC'),
            'session_duration': time.time() - session.get('start_time', time.time()),
            'previous_interactions': getattr(session, 'interaction_history', [])
        }
        
        # Process with context
        intent, entities = gpt_agent.process_input(user_input)
        
        # Store interaction history
        if not hasattr(session, 'interaction_history'):
            session['interaction_history'] = []
        session['interaction_history'].append({
            'input': user_input,
            'intent': intent,
            'timestamp': datetime.now().isoformat()
        })
        
        return intent, entities
        
    except Exception as e:
        logger.error(f"💥 GPT processing error: {e}")
        raise





async def process_audio_chunks(websocket, audio_chunks, timezone, voice_to_text, gpt_agent, text_to_voice, calendar_service):
    """Process audio chunks through the complete pipeline: STT -> GPT -> Calendar -> TTS"""
    try:
        # Combine all audio chunks
        combined_audio = b''.join(audio_chunks)
        logger.info(f"🔊 Processing {len(combined_audio)} bytes of combined audio data")
        
        # Step 1: STT - Convert audio to text
        logger.info("🎙️ Step 1: Converting speech to text...")
        user_input = voice_to_text.recognize(combined_audio).strip()
        
        if not user_input:
            logger.warning("⚠️ STT returned empty result")
            audio_response = text_to_voice.synthesize(
                "Sorry, I didn't catch that. Could you please repeat?"
            )
            await websocket.send_json({"audio": audio_response.hex()})
            return
        
        logger.info(f"👤 You said: '{user_input}'")
        
        # Check for exit commands
        if any(cmd in user_input.lower() for cmd in EXIT_COMMANDS):
            logger.info("👋 Exit command detected")
            goodbye = "Thanks for using the voice assistant. Have a great day!"
            audio_response = text_to_voice.synthesize(goodbye)
            await websocket.send_json({
                "audio": audio_response.hex(), 
                "message": "👋 Exiting",
                "exit": True
            })
            return
        
        # Step 2: GPT - Process with AI agent
        logger.info("🤖 Step 2: Processing with GPT agent...")
        intent, entities = gpt_agent.process_input(user_input)
        logger.info(f"🤖 GPT Result: intent={intent}, entities={entities}")
        
        if intent != "schedule_meeting":
            response_text = entities.get("reply", "I didn't understand that. Please try again.")
            logger.info(f"🔄 Non-scheduling intent, responding: {response_text}")
            audio_response = text_to_voice.synthesize(response_text)
            await websocket.send_json({
                "audio": audio_response.hex(), 
                "message": response_text
            })
            return
        
        # Add timezone to entities for calendar operations
        entities['timezone'] = timezone
        
        # Step 3: Calendar - Fill missing fields and schedule meeting
        logger.info("📅 Step 3: Processing calendar scheduling...")
        try:
            gpt_result = fill_missing_fields(entities, text_to_voice, websocket)
            result = calendar_service.intelligent_schedule_handler(gpt_result)
            
            # Step 4: TTS - Generate audio response
            logger.info("🗣️ Step 4: Generating audio response...")
            audio_response = handle_scheduling(result, text_to_voice)
            
            logger.info(f"✅ Scheduling result: {result['status']}")
            await websocket.send_json({
                "status": result['status'],
                "event": result,
                "audio": audio_response.hex()
            })
            
            # Log the interaction
            try:
                with open("data/logs/interaction.log", "a") as log_file:
                    log_file.write(f"{datetime.now()}: {json.dumps(result)}\n")
            except:
                pass  # Don't fail if logging fails
                
        except Exception as e:
            logger.error(f"💥 Error in calendar scheduling: {str(e)}")
            audio_response = text_to_voice.synthesize(f"Sorry, there was an error scheduling your meeting: {str(e)}")
            await websocket.send_json({
                "audio": audio_response.hex(), 
                "error": str(e)
            })
    
    except Exception as e:
        logger.error(f"💥 Error in audio processing pipeline: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        audio_response = text_to_voice.synthesize(
            "Sorry, I had trouble processing your request. Please try again."
        )
        await websocket.send_json({
            "audio": audio_response.hex(), 
            "error": "Audio processing failed"
        })
@app.get("/calendar/availability")
async def get_availability1(start: str, end: str, timezone: str,entities: dict, websocket: WebSocket, session: dict):
    try:
        # Enhanced field completion
        completed_entities = await fill_missing_fields_async(entities, text_to_voice, websocket, session)
        
        # Schedule the meeting
        result = calendar_service.intelligent_schedule_handler(completed_entities)
        
        if result.get('status') == 'success':
            meeting_details = result.get('event_details', {})
            response_text = (f"Perfect! I've successfully scheduled your meeting "
                           f"'{meeting_details.get('title', 'Meeting')}' "
                           f"for {meeting_details.get('start', 'the requested time')}. "
                           f"You'll receive a confirmation shortly.")
        else:
            error_msg = result.get('message', 'Unknown error occurred')
            response_text = f"I couldn't schedule the meeting: {error_msg}. Would you like to try with different details?"
        
        await send_audio_response(websocket, response_text, "meeting_result", session, {
            "status": result.get('status', 'error'),
            "event_details": result
        })
        
        # Enhanced logging
        log_interaction(result, session)
        
    except Exception as e:

        logger.error(f"💥 Meeting scheduling error for {session['id']}: {str(e)}")
        await send_error_response(websocket, f"Scheduling failed: {str(e)}")

    
@app.get("/calendar/test1")
async def test_availability(start: str, end: str, timezone: str):
    logger.info(f"🔍 GET /calendar/availability called")
    logger.info(f"📅 Parameters: start={start}, end={end}, timezone={timezone}")
    
    try:
        # Check if calendar_service exists
        if not hasattr(globals(), 'calendar_service') or calendar_service is None:
            logger.error("❌ calendar_service is not initialized")
            raise HTTPException(status_code=500, detail="Calendar service not initialized")
        
        logger.info("📞 Calling calendar_service.get_availability...")
        availability = calendar_service.get_availability(start, end, timezone)
        
        logger.info(f"✅ Successfully got {len(availability)} events")
        logger.info(f"🔍 First event (if any): {availability[0] if availability else 'None'}")
        
        return {"availability": availability}
        
    except ValueError as ve:
        logger.error(f"❌ ValueError in get_availability: {str(ve)}")
        logger.error(f"🔍 Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(ve)}")
        
    except Exception as e:
        logger.error(f"❌ Unexpected error in get_availability: {str(e)}")
        logger.error(f"🔍 Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Also add this to test calendar_service initialization
@app.get("/calendar/test")
async def test_calendar_service():
    try:
        logger.info("🧪 Testing calendar service...")
        
        if not hasattr(globals(), 'calendar_service'):
            return {"status": "error", "message": "calendar_service not in globals"}
        
        if calendar_service is None:
            return {"status": "error", "message": "calendar_service is None"}
            
        # Test basic functionality
        test_start = "2025-08-16T10:00:00Z"
        test_end = "2025-08-16T11:00:00Z"
        test_timezone = "UTC"
        
        logger.info(f"🧪 Testing with: {test_start} to {test_end} in {test_timezone}")
        result = calendar_service.test_availability(test_start, test_end, test_timezone)
        
        return {
            "status": "success", 
            "message": f"Calendar service working. Found {len(result)} events",
            "sample_result": result[:1] if result else []
        }
        
    except Exception as e:
        logger.error(f"❌ Calendar service test failed: {str(e)}")
        logger.error(f"🔍 Full traceback: {traceback.format_exc()}")
        return {
            "status": "error", 
            "message": str(e),
            "traceback": traceback.format_exc()
        }
@app.get("/calendar/events")
async def get_events(start: str, end: str, timezone: str,entities , websocket: WebSocket, session: dict):
    """
    Fetch calendar events within the specified date range, returning titles and times
    converted to the specified timezone (default: Asia/Kolkata).
    
    Args:
        start (str): Start of the date range in ISO format (e.g., 2025-08-06T00:00:00Z)
        end (str): End of the date range in ISO format (e.g., 2025-08-13T23:59:59Z)
        timezone (str): Target timezone for event times (default: Asia/Kolkata)
    
    Returns:
        dict: List of events with titles, start, and end times
    """

    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fill_missing_fields, entities, text_to_voice, websocket)
    except Exception as e:
        logger.error(f"Error in fill_missing_fields for {session['id']}: {e}")
        return entities

def validate_audio_buffer_quality(audio_buffer: bytearray) -> dict:
    """Comprehensive audio quality validation"""
    try:
        if len(audio_buffer) < SAMPLE_RATE * BYTES_PER_SAMPLE * 0.5:  # Less than 0.5 seconds
            return {'is_valid': False, 'reason': 'Audio too short (minimum 0.5 seconds required)'}
        
        # Convert to numpy array for analysis
        samples = np.frombuffer(audio_buffer, dtype=np.int16)
        
        # Check for silence
        max_amplitude = np.max(np.abs(samples))
        if max_amplitude < 100:
            return {'is_valid': False, 'reason': 'Audio too quiet or silent'}
        
        # Check for clipping
        clipping_ratio = np.sum(np.abs(samples) > 30000) / len(samples)
        if clipping_ratio > 0.1:  # More than 10% clipped
            return {'is_valid': False, 'reason': 'Audio is heavily clipped/distorted'}
        
        # Calculate overall quality metrics
        rms = np.sqrt(np.mean(samples.astype(np.float32)**2))
        dynamic_range = max_amplitude / max(rms, 1)
        
        if rms < 200:
            return {'is_valid': False, 'reason': 'Audio level too low'}
        
        return {
            'is_valid': True, 
            'quality_score': min(100, int(rms / 50)),
            'dynamic_range': dynamic_range
        }
        
    except Exception as e:
        logger.error(f"💥 Audio quality validation error: {e}")
        return {'is_valid': False, 'reason': 'Unable to analyze audio quality'}

async def save_pcm_as_wav(audio_buffer: bytearray) -> Optional[str]:
    """Save PCM audio buffer as WAV file with proper headers"""
    try:
        logger.info(f"💾 Creating WAV file from {len(audio_buffer)} bytes of PCM data")
        if len(audio_buffer) == 0:
            logger.error("❌ Cannot create WAV file: audio buffer is empty!")
            return None
        temp_fd, temp_path = tempfile.mkstemp(suffix='.wav', prefix='voice_assistant_')
        
        with os.fdopen(temp_fd, 'wb') as f:
            # Write WAV file using wave module for proper formatting
            with wave.open(f, 'wb') as wav_file:
                wav_file.setnchannels(CHANNELS)
                wav_file.setsampwidth(BYTES_PER_SAMPLE)
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.writeframes(audio_buffer)
                logger.info(f"📝 Writing {len(audio_buffer)} bytes to WAV file")
                # wav_file.writeframes(audio_buffer)
        # Verify file was created successfully
        if os.path.exists(temp_path):
            file_size = os.path.getsize(temp_path)
            logger.info(f"📁 Created WAV file: {temp_path} ({file_size} bytes)")
            if file_size <= 44:  # WAV header is 44 bytes
                logger.error(f"❌ WAV file is too small ({file_size} bytes) - likely empty!")
                return None
            return temp_path
        
        return None
        
    except Exception as e:
        logger.error(f"💥 Error saving PCM as WAV: {e}")
        return None

async def send_audio_response(websocket: WebSocket, text: str, response_type: str, 
                            session: dict, extra_data: dict = None):
    """Enhanced audio response with better synthesis and error handling"""
    try:
        response_data = {
            "type": response_type,
            "message": text,
            "session_id": session['id'],
            "timestamp": datetime.now().isoformat()
        }
        
        if extra_data:
            response_data.update(extra_data)
        
        # Enhanced audio synthesis
        try:
            audio_response = text_to_voice.synthesize(text)
            logger.info(f"🔊 Synthesized audio for response [{session['id']}]: {len(audio_response)} bytes")
            if audio_response and len(audio_response) > 0:
                response_data["audio"] = audio_response.hex()
                response_data["audio_duration"] = estimate_audio_duration(audio_response)
        except Exception as audio_error:
            logger.warning(f"⚠️ Audio synthesis failed for {session['id']}: {audio_error}")
            # Continue without audio
        
        await websocket.send_json(response_data)
        logger.info(f"🗣️ Sent response [{session['id']}]: {response_type}")
        
    except Exception as e:
        logger.error(f"💥 Error sending response to {session['id']}: {e}")

async def send_error_response(websocket: WebSocket, error_message: str, session: dict = None):
    """Send standardized error response"""
    session_id = session['id'] if session else 'unknown'
    await send_audio_response(websocket, f"Sorry, {error_message}", "error", 
                            session or {'id': session_id})

def estimate_audio_duration(audio_data: bytes) -> float:
    """Estimate audio duration from synthesized audio"""
    try:
        # This is a rough estimate - actual implementation would depend on TTS format
        return len(audio_data) / (SAMPLE_RATE * BYTES_PER_SAMPLE)
    except:
        return 0.0

async def cancel_recording(websocket: WebSocket, session: dict):
    """Cancel recording with proper cleanup"""
    try:
        session['is_recording'] = False
        session['processing'] = False
        session['audio_buffer'].clear()
        session['chunk_count'] = 0
        session['total_audio_duration'] = 0
        
        if session['silence_timer']:
            session['silence_timer'].cancel()
            session['silence_timer'] = None
        
        logger.info(f"❌ Recording cancelled for {session['id']}")
        
        await websocket.send_json({
            "type": "recording_cancelled",
            "message": "Recording cancelled successfully",
            "session_id": session['id']
        })
        
    except Exception as e:

        logger.error(f"💥 Error cancelling recording for {session['id']}: {e}")

async def cleanup_session(session: dict):
    """Enhanced session cleanup"""
    try:
        session_id = session.get('id', 'unknown')
        logger.info(f"🧹 Cleaning up session {session_id}")
        
        if session.get('silence_timer'):
            session['silence_timer'].cancel()
        
        for temp_file in session.get('temp_files', []):
            cleanup_temp_file(temp_file)
        
        # Clear all session data
        session.clear()
        
    except Exception as e:
        logger.error(f"💥 Error during cleanup: {e}")

def cleanup_temp_file(file_path: str):
    """Enhanced temp file cleanup with retry mechanism"""
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
                logger.debug(f"🗑️ Cleaned up: {file_path}")
                return
        except PermissionError:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Cleanup attempt {attempt + 1} failed, retrying...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.warning(f"⚠️ Failed to cleanup {file_path} after {max_retries} attempts")
        except Exception as e:
            logger.warning(f"⚠️ Failed to cleanup {file_path}: {e}")
            break

def log_interaction(result: dict, session: dict):
    """Enhanced interaction logging"""
    try:
        log_dir = "data/logs"
        os.makedirs(log_dir, exist_ok=True)
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session.get('id'),
            "timezone": session.get('timezone'),
            "audio_duration": session.get('total_audio_duration'),
            "result": result
        }
        
        # Daily log files
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file_path = f"{log_dir}/interactions_{date_str}.log"
        
        with open(log_file_path, "a", encoding='utf-8') as log_file:
            log_file.write(f"{json.dumps(log_entry, ensure_ascii=False)}\n")
            
    except Exception as e:
        logger.warning(f"⚠️ Failed to log interaction: {e}")


@app.get("/debug", response_class=HTMLResponse)
async def debug_dashboard():
    html_content = f"""
    <html>
    <head><title>Voice Assistant Debug Dashboard</title></head>
    <body>
        <h1>🐛 Debug Dashboard</h1>
        <h2>Active Sessions: {len(active_sessions)}</h2>
        <div id="sessions">
        {"".join([f'''
            <div style="border:1px solid #ccc; margin:10px; padding:10px;">
                <h3>Session: {sid}</h3>
                <p>Recording: {session.get('is_recording', False)}</p>
                <p>Processing: {session.get('processing', False)}</p>
                <p>Buffer: {len(session.get('audio_buffer', []))} bytes</p>
                <p>Duration: {session.get('total_audio_duration', 0):.2f}s</p>
            </div>
        ''' for sid, session in active_sessions.items()])}
        </div>
        <script>setTimeout(() => location.reload(), 2000);</script>
    </body>
    </html>
    """
    return html_content

# Health check and monitoring endpoints
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "active_sessions": len(active_sessions),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/sessions")
async def get_sessions():
    return {
        "active_sessions": len(active_sessions),
        "sessions": [
            {
                "id": session_id,
                "is_recording": session.get('is_recording', False),
                "processing": session.get('processing', False),
                "audio_duration": session.get('total_audio_duration', 0)
            }
            for session_id, session in active_sessions.items()
        ]
    }
def debug_session_state(session: dict, e: str):
    """Debug session state for audio processing"""
    # logger.info(f"🔍 DEBUG SESSION STATE [{event}]:")
    logger.info(f"   📊 Session ID: {session.get('id', 'unknown')}")
    logger.info(f"   📊 Recording: {session.get('is_recording', False)}")
    logger.info(f"   📊 Processing: {session.get('processing', False)}")
    logger.info(f"   📊 Buffer size: {len(session.get('audio_buffer', []))} bytes")
    logger.info(f"   📊 Chunk count: {session.get('chunk_count', 0)}")
    logger.info(f"   📊 Duration: {session.get('total_audio_duration', 0):.2f}s")
    
    # Sample first few bytes of buffer
    if session.get('audio_buffer'):
        sample = session['audio_buffer'][:10]
        logger.info(f"   📊 Buffer sample: {[hex(b) for b in sample]}")

        raise HTTPException(status_code=500, detail=f"Error fetching events: {str(e)}")


@app.post("/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    # Save uploaded WAV file
    with open("temp.wav", "wb") as f:
        f.write(await file.read())

    # Configure Azure Speech
    speech_config = speechsdk.SpeechConfig(
        subscription=config.azure_speech_key,
        region=config.azure_speech_region
    )
    audio_input = speechsdk.audio.AudioConfig(filename="temp.wav")

    # Recognize speech
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, audio_config=audio_input
    )
    result = speech_recognizer.recognize_once()
    
    return {"text": result.text}
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info",
        access_log=True
    )