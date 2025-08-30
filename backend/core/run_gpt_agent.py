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
    
    def process_input(self, text: str, context: dict) -> tuple[str, dict]:
            try:
                current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                current_time = datetime.datetime.now().strftime("%H:%M:%S")
                user_timezone = context.get('timezone', 'UTC')
                partial_details = context.get('partial_meeting_details', {})
                
                # --- THIS IS THE UPGRADE ---
                # We now format the full conversation history for the AI to see.
                previous_interactions = context.get('previous_interactions', [])
                history_str = "\n".join([
                    f"- User said: \"{turn['input']}\" (AI interpreted intent: {turn['intent']})" 
                    for turn in previous_interactions
                ])
                if not history_str:
                    history_str = "No previous conversation history."
                # --- END OF UPGRADE ---
    
                self.logger.info(f"Processing input: '{text}' (History: {len(previous_interactions)} turns)")
                
                prompt = f"""
                You are a stateful, context-aware voice assistant for scheduling meetings.
                Your goal is to complete the meeting details by having a natural conversation.
    
                # Context
                - Current date is: {current_date}
                - User's timezone is: {user_timezone}
    
                # Conversation History (Most recent is last)
                {history_str}
    
                # Details Gathered So Far
                {json.dumps(partial_details)}
    
                # Instructions
                1.  Analyze the user's VERY LATEST input: "{text}".
                2.  Refer to the 'Conversation History' and 'Details Gathered So Far' to understand the full context.
                3.  The user's latest input might be an ANSWER to a previous question, a CORRECTION, or a new piece of information.
                4.  Intelligently combine the user's latest input with the details already gathered.
                5.  If the user says "with John" and the title is empty, set the title to "Meeting with John".
                6.  If the user corrects a detail (e.g., "no, make it 5 PM"), update the existing detail.
                7.  Your final output must be a single JSON object with the most up-to-date entities.

                # Intent Mapping
                - If user wants to book/create: intent='schedule_meeting'.
                - If user wants to cancel/delete: intent='cancel_meeting'.
                - If user wants to move/change time/date: intent='reschedule_meeting'.
                - If user asks to list meetings for a specific day (e.g., "get the meetings on this day"), infer the date from context or require 'date', and set intent='get_meetings_day'.

                # JSON Output Format
                - intent: one of 'schedule_meeting' | 'cancel_meeting' | 'reschedule_meeting' | 'get_meetings_day' | 'other'.
                - entities:
                  - For cancellation: {"title?","date?","time?","timezone?"} (allow by title only, or by date+time)
                  - For reschedule: {"title?","date?","time?","timezone?","new_date","new_time"}
                  - For day listing: {"date","timezone?"}
                """
    
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": prompt},
                    
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
                return "other", {"reply": "I had an issue processing your request with the AI model."}