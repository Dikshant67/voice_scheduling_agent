from openai import OpenAI,AzureOpenAI
import logging
from config.config import Config
import json
import os
import datetime

class GPTAgent:
    def __init__(self, api_key: str):
        if not api_key:
            raise Exception("OpenAI API key not set in environment variables.")
       
        self.client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"))
        self.logger = logging.getLogger(__name__)
        
        self.date = datetime.datetime.now().strftime("%Y-%m-%d")  # 2025-08-19
        self.time = datetime.datetime.now().strftime("%H:%M:%S")  # 16:54:30
    
    def process_input(self, text: str) -> tuple[str, dict]:
        try:
            self.logger.info(f"Processing input: {text}")
            prompt = """
            You are a voice assistant for scheduling meetings. Extract the intent and entities from the user's input. 
            The intent should be 'schedule_meeting' for scheduling requests or 'other' for unrelated requests.
            consider todays date is {date}  and time is {time}
            Entities should include:
            - title: Meeting title (string)
            - date: Date in YYYY-MM-DD format (string)
            - time: Time in HH:MM format (string)
            - timezone: IANA timezone (e.g., 'America/New_York', optional)
            - attendees: List of attendee names or emails (list, optional)
            - reply: A natural language response for non-scheduling intents (string, optional)
            
            Return the result as a JSON object with 'intent' and 'entities' keys.
            Example input: "Schedule a meeting with John tomorrow at 3 PM in New York time"
            Example output: {
                "intent": "schedule_meeting",
                "entities": {
                    "title": "Meeting with John",
                    "date": "2025-08-07",
                    "time": "15:00",
                    "timezone": "America/New_York",
                    "attendees": ["John"]
                }
            }
            """
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            intent = result.get("intent", "other")
            entities = result.get("entities", {})
            self.logger.info(f"GPT Result: intent={intent}, entities={entities}")
            return intent, entities
        except Exception as e:
            self.logger.error(f"GPT error: {str(e)}")
            return "other", {"reply": f"Error processing request: {str(e)}"}