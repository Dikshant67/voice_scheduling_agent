from fastapi import FastAPI, WebSocket, HTTPException
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

# Exit commands
EXIT_COMMANDS = ["stop", "exit", "quit", "bye", "goodbye", "that's it", "cancel", "okay"]

@app.get("/", tags=["root"])
async def read_root():
    return {"message": "Voice-based Meeting Scheduler API"}

@app.websocket("/ws/voice")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        await websocket.send_json({"message": "🎤 Voice Assistant is ready. Say something to schedule a meeting!"})
        while True:
            data = await websocket.receive_json()
            audio_data = bytes.fromhex(data.get('audio', ''))
            timezone = data.get('timezone', 'UTC')
            logger.info(f"Received audio data with timezone: {timezone}")

            user_input = voice_to_text.recognize(audio_data).strip().lower()
            if not user_input:
                audio_response = text_to_voice.synthesize("Sorry, I didn't catch that. Could you please repeat?")
                await websocket.send_json({"audio": audio_response.hex()})
                continue

            logger.info(f"👤 You said: {user_input}")

            if any(cmd in user_input for cmd in EXIT_COMMANDS):
                goodbye = "Thanks for using the voice assistant. Have a great day!"
                audio_response = text_to_voice.synthesize(goodbye)
                await websocket.send_json({"audio": audio_response.hex(), "message": "👋 Exiting"})
                break

            intent, entities = gpt_agent.process_input(user_input)
            logger.info(f"🤖 GPT Result: intent={intent}, entities={entities}")

            if intent != "schedule_meeting":
                response_text = entities.get("reply", "I didn't understand that. Please try again.")
                audio_response = text_to_voice.synthesize(response_text)
                await websocket.send_json({"audio": audio_response.hex(), "message": response_text})
                continue

            entities['timezone'] = timezone

            try:
                gpt_result = fill_missing_fields(entities, text_to_voice, websocket)
                result = calendar_service.intelligent_schedule_handler(gpt_result)
                audio_response = handle_scheduling(result, text_to_voice)
                
                await websocket.send_json({
                    "status": result['status'],
                    "event": result,
                    "audio": audio_response.hex()
                })
                
                with open("data/logs/interaction.log", "a") as log_file:
                    log_file.write(f"Scheduled: {json.dumps(result)}\n")
                
            except Exception as e:
                logger.error(f"Error scheduling meeting: {str(e)}")
                audio_response = text_to_voice.synthesize(f"Error: {str(e)}")
                await websocket.send_json({"audio": audio_response.hex(), "error": str(e)})

    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        audio_response = text_to_voice.synthesize("Connection error. Please try again.")
        await websocket.send_json({"audio": audio_response.hex(), "error": "Connection error"})
    finally:
        await websocket.close()

@app.get("/calendar/availability")
async def get_availability(start: str, end: str, timezone: str):
    try:
        availability = calendar_service.get_availability(start, end, timezone)
        return {"availability": availability}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)