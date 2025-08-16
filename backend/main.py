import azure.cognitiveservices.speech as speechsdk
import traceback
from fastapi import FastAPI, File, UploadFile, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio
from core.calendar_service import CalendarService
from core.voice_to_text import VoiceToText
from core.text_to_voice import TextToVoice
from core.run_gpt_agent import GPTAgent
from core.validation import validate_meeting_details
from core.conversation_flow import fill_missing_fields, handle_scheduling
from core.timezone_utils import parse_datetime, validate_timezone
from config.config import Config
import logging
import json
from datetime import datetime
import pytz

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS configuration for frontend
origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
config = Config()
calendar_service = CalendarService()
voice_to_text = VoiceToText(config.azure_speech_key, config.azure_speech_region)
text_to_voice = TextToVoice(config.azure_speech_key, config.azure_speech_region)
gpt_agent = GPTAgent(config.gpt_api_key)
time=datetime.now()  # Initialize current time for logging
# Exit commands
EXIT_COMMANDS = ["stop", "exit", "quit", "bye", "goodbye", "that's it", "cancel", "okay"]

@app.get("/", tags=["root"])
async def read_root():
    return {"message": "Voice-based Meeting Scheduler API"}

# @app.websocket("/ws/voice")
# async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    audio_chunks = []
    timezone = "UTC"
    recording_active = False
    
    try:
        await websocket.send_json({
            "message": "🎤 Voice Assistant is ready. Say something to schedule a meeting!"
        })
        
        while True:
            try:
                # Try to receive JSON message first
                data = await websocket.receive_json()
                
                if data.get("event") == "start":
                    timezone = data.get('timezone', 'UTC')
                    audio_chunks = []  # Reset audio chunks
                    recording_active = True
                    logger.info(f"Started recording with timezone: {timezone}")
                    
                elif data.get("event") == "end":
                    recording_active = False
                    logger.info("Recording ended, processing audio...")
                    
                    # Process accumulated audio chunks
                    if audio_chunks:
                        try:
                            # Combine all audio chunks
                            combined_audio = b''.join(audio_chunks)
                            logger.info(f"Processing {len(combined_audio)} bytes of audio data")
                            
                            # Convert audio to text
                            user_input = voice_to_text.recognize(combined_audio).strip().lower()
                            
                            if not user_input:
                                audio_response = text_to_voice.synthesize(
                                    "Sorry, I didn't catch that. Could you please repeat?"
                                )
                                await websocket.send_json({"audio": audio_response.hex()})
                                continue
                            
                            logger.info(f"👤 You said: {user_input}")
                            
                            # Check for exit commands
                            if any(cmd in user_input for cmd in EXIT_COMMANDS):
                                goodbye = "Thanks for using the voice assistant. Have a great day!"
                                audio_response = text_to_voice.synthesize(goodbye)
                                await websocket.send_json({
                                    "audio": audio_response.hex(), 
                                    "message": "👋 Exiting",
                                    "exit": True
                                })
                                break
                            
                            # Process with GPT agent
                            intent, entities = gpt_agent.process_input(user_input)
                            logger.info(f"🤖 GPT Result: intent={intent}, entities={entities}")
                            
                            if intent != "schedule_meeting":
                                response_text = entities.get("reply", "I didn't understand that. Please try again.")
                                audio_response = text_to_voice.synthesize(response_text)
                                await websocket.send_json({
                                    "audio": audio_response.hex(), 
                                    "message": response_text
                                })
                                continue
                            
                            # Add timezone to entities
                            entities['timezone'] = timezone
                            
                            # Fill missing fields and schedule meeting
                            try:
                                gpt_result = fill_missing_fields(entities, text_to_voice, websocket)
                                result = calendar_service.intelligent_schedule_handler(gpt_result)
                                audio_response = handle_scheduling(result, text_to_voice)
                                
                                await websocket.send_json({
                                    "status": result['status'],
                                    "event": result,
                                    "audio": audio_response.hex()
                                })
                                
                                # Log the interaction
                                with open("data/logs/interaction.log", "a") as log_file:
                                    log_file.write(f"Scheduled: {json.dumps(result)}\n")
                                    
                            except Exception as e:
                                logger.error(f"Error scheduling meeting: {str(e)}")
                                audio_response = text_to_voice.synthesize(f"Error: {str(e)}")
                                await websocket.send_json({
                                    "audio": audio_response.hex(), 
                                    "error": str(e)
                                })
                        
                        except Exception as e:
                            logger.error(f"Error processing audio: {str(e)}")
                            audio_response = text_to_voice.synthesize(
                                "Sorry, I had trouble processing your audio. Please try again."
                            )
                            await websocket.send_json({
                                "audio": audio_response.hex(), 
                                "error": "Audio processing failed"
                            })
                    else:
                        # No audio chunks received
                        audio_response = text_to_voice.synthesize(
                            "I didn't receive any audio. Please try speaking again."
                        )
                        await websocket.send_json({"audio": audio_response.hex()})
                
            except Exception as json_error:
                # If JSON parsing fails, try to receive binary data
                try:
                    if recording_active:
                        audio_data = await websocket.receive_bytes()
                        audio_chunks.append(audio_data)
                        logger.info(f"Received audio chunk: {len(audio_data)} bytes")
                    else:
                        # Received binary data but not recording
                        logger.warning("Received binary data but recording is not active")
                        
                except Exception as binary_error:
                    logger.error(f"Error receiving data: JSON={json_error}, Binary={binary_error}")
                    break
                    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            audio_response = text_to_voice.synthesize("Connection error. Please try again.")
            await websocket.send_json({
                "audio": audio_response.hex(), 
                "error": "Connection error"
            })
        except:
            pass  # Connection might be already closed
    finally:
        try:
            await websocket.close()
        except:
            pass
@app.websocket("/ws/voice")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("INFO:     connection open")
    
    audio_chunks = []
    timezone = "UTC"
    recording_active = False
    
    try:
        await websocket.send_json({
            "message": "🎤 Voice Assistant is ready. Say something to schedule a meeting!"
        })
        
        while True:
            try:
                # Use receive() instead of receive_json() to handle both text and binary
                data = await websocket.receive()
                
                if "text" in data:
                    # Handle JSON messages
                    try:
                        message = json.loads(data["text"])
                        logger.info(f"📨 Received JSON: {message}")
                        
                        if message.get("event") == "start":
                            timezone = message.get('timezone', 'UTC')
                            audio_chunks = []
                            recording_active = True
                            logger.info(f"▶️ Started recording with timezone: {timezone}")
                            
                        elif message.get("event") == "end":
                            recording_active = False
                            logger.info(f"⏹️ Recording ended, processing {len(audio_chunks)} audio chunks...")
                            
                            if audio_chunks:
                                await process_audio_chunks(
                                    websocket, audio_chunks, timezone, 
                                    voice_to_text, gpt_agent, text_to_voice, calendar_service
                                )
                            else:
                                logger.warning("⚠️ No audio chunks received")
                                audio_response = text_to_voice.synthesize(
                                    "I didn't receive any audio. Please try speaking again."
                                )
                                await websocket.send_json({"audio": audio_response.hex()})
                                
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Invalid JSON received: {e}")
                        continue
                
                elif "bytes" in data and recording_active:
                    # Handle binary audio data
                    audio_data = data["bytes"]
                    audio_chunks.append(audio_data)
                    logger.info(f"🎵 Received audio chunk: {len(audio_data)} bytes (Total chunks: {len(audio_chunks)})")
                    
                elif "bytes" in data and not recording_active:
                    logger.warning("⚠️ Received binary data but recording is not active")
                    
            except WebSocketDisconnect:
                logger.info("INFO:     connection closed")
                break
            except Exception as e:
                logger.error(f"💥 Error receiving data: {e}")
                # Don't break immediately, try to continue
                continue
                
    except WebSocketDisconnect:
        logger.info("INFO:     connection closed")
    except Exception as e:
        logger.error(f"💥 WebSocket error: {e}")
        try:
            audio_response = text_to_voice.synthesize("Connection error. Please try again.")
            await websocket.send_json({
                "audio": audio_response.hex(), 
                "error": "Connection error"
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


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
async def get_availability1(start: str, end: str, timezone: str):
    try:
        availability = calendar_service.get_availability(start, end, timezone)
        return {"availability": availability}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
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
async def get_events(start: str, end: str, timezone: str = "Asia/Kolkata"):
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
        # Parse and validate input dates
        start_dt = parse_datetime(start)
        end_dt = parse_datetime(end)
        validate_timezone(timezone)

        # Fetch events using CalendarService
        events = calendar_service.fetch_existing_events(start_dt, end_dt, timezone)
        
        # Return events in a clean format
        return {
            "events": [
                {
                    "title": event["title"],
                    "start": event["start"],
                    "end": event["end"]
                } for event in events
            ]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching events: {str(e)}")
@app.get("/test/tts")
async def test_tts():
    """Test endpoint to verify TTS is working"""
    try:
        test_text = "Hello, this is a test of the text to speech system"
        audio_data = text_to_voice.synthesize(test_text)
        return {
            "status": "success",
            "message": "TTS working",
            "audio_size": len(audio_data),
            "audio": audio_data.hex()
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}    

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
    uvicorn.run(app, host="0.0.0.0", port=8000)