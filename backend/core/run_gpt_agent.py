# In core/run_gpt_agent.py

from openai import AzureOpenAI
import logging
import json
import os
import datetime

class GPTAgent:
    def __init__(self): # <-- CHANGE: Removed unused api_key parameter
        # This part is correct, it loads settings from your environment
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.logger = logging.getLogger(__name__)
        # <-- CHANGE: Removed the stale self.date and self.time from here

    # <-- CHANGE: The method now accepts the 'context' dictionary
    def process_input(self, text: str, context: dict) -> tuple[str, dict]:
        try:
            # <-- CHANGE: Get date, time, and timezone for EACH request
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            current_time = datetime.datetime.now().strftime("%H:%M:%S")
            user_timezone = context.get('timezone', 'UTC') # Get timezone from context

            self.logger.info(f"Processing input with context: '{text}' (Timezone: {user_timezone})")
            
            # <-- CHANGE: Converted the prompt to an f-string to inject real-time data
            prompt = f"""
            You are a highly intelligent voice assistant for scheduling meetings.
            Your task is to accurately extract the intent and entities from the user's request.
            The intent must be either 'schedule_meeting' or 'other'.

            IMPORTANT CONTEXT:
            - The current date is: {current_date}
            - The current time is: {current_time}
            - The user's local timezone is: {user_timezone}

            When the user says "tomorrow", you must calculate the correct date based on the current date.
            When the user gives a relative time like "in 2 hours", calculate it based on the current time.
            If the user does not specify a title, create a sensible one like "Meeting with [Attendees]".

            Entities to extract:
            - title: Meeting title (string)
            - date: Date in YYYY-MM-DD format (string).
            - time: Time in HH:MM format (24-hour clock) (string).
            - attendees: List of attendee names or emails (list of strings, optional).
            - reply: A polite, natural language response ONLY if the intent is 'other' (string, optional).

            You MUST return the result as a single, well-formed JSON object with 'intent' and 'entities' keys.

            Example 1:
            User input: "Schedule a meeting with John tomorrow at 3 PM"
            Output: {{
                "intent": "schedule_meeting",
                "entities": {{
                    "title": "Meeting with John",
                    "date": "{ (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d') }",
                    "time": "15:00",
                    "attendees": ["John"]
                }}
            }}

            Example 2:
            User input: "what's the weather like"
            Output: {{
                "intent": "other",
                "entities": {{
                    "reply": "I can only help with scheduling meetings. I can't check the weather for you."
                }}
            }}
            """

            response = self.client.chat.completions.create(
                model="gpt-4o", # Or your preferred model
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
            self.logger.error(f"GPT error: {str(e)}", exc_info=True)
            return "other", {"reply": f"I had an issue processing your request with the AI model."}