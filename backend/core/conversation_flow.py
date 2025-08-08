from core.validation import is_valid_date, is_valid_time
from core.text_to_voice import TextToVoice
from fastapi import WebSocket

async def fill_missing_fields(gpt_result: dict, tts: TextToVoice, websocket: WebSocket) -> dict:
    if gpt_result.get("intent") != "schedule_meeting":
        return gpt_result

    # Extract fields
    title = gpt_result.get("title", "").strip()
    date_str = gpt_result.get("date", "").strip()
    time_str = gpt_result.get("time", "").strip()
    timezone = gpt_result.get("timezone", "UTC")

    if not title:
        audio_response = tts.synthesize("Please provide the meeting title.")
        await websocket.send_json({"audio": audio_response.hex(), "message": "Please provide the meeting title."})
        # Note: For simplicity, we assume the frontend will send the missing field in the next request
        gpt_result["title"] = ""  # Placeholder; actual implementation may need additional WebSocket messages

    if not is_valid_date(date_str):
        audio_response = tts.synthesize("Please provide a valid date in YYYY-MM-DD format.")
        await websocket.send_json({"audio": audio_response.hex(), "message": "Please provide a valid date."})
        gpt_result["date"] = ""

    if not is_valid_time(time_str):
        audio_response = tts.synthesize("Please provide a valid time in HH:MM format.")
        await websocket.send_json({"audio": audio_response.hex(), "message": "Please provide a valid time."})
        gpt_result["time"] = ""

    return gpt_result

def handle_scheduling(result: dict, tts: TextToVoice) -> bytes:
    if result['status'] == 'scheduled':
        response_text = f"✅ Your meeting has been scheduled from {result['start']} to {result['end']} in {result['timezone']}."
    elif result['status'] == 'conflict':
        response_text = f"⚠️ There's a conflict with your calendar. Would you prefer {result['suggested_start']} in {result['timezone']} instead?"
    elif result['status'] == 'missing_info':
        response_text = result['message']
    else:
        response_text = "❌ Something went wrong while scheduling. Please try again."
    return tts.synthesize(response_text)
# # voice_pipeline/loop_conversation.py
# # from utils import is_valid_date, is_valid_time, ask_for_missing_info
# # from core.voice_to_text import listen_and_transcribe
# # from core.run_gpt_agent import run_gpt_agent
# # from core.text_to_voice import speak_text
# # from flow.conversation_flow import intelligent_schedule_handler
# import sys
# import os


# from run_gpt_agent import run_gpt_agent
# from validation import is_valid_date, is_valid_time
# # from calendar_service import load_calendar_service 
# from voice_to_text import listen_and_transcribe
# from text_to_voice import speak_text
# from validation import is_valid_date, is_valid_time
# from utils import ask_for_field
# from calendar_service import intelligent_schedule_handler
# EXIT_COMMANDS = ["stop", "exit", "quit", "bye", "goodbye", "that's it", "cancel","Okay"]
# REQUIRED_FIELDS = ['title', 'date', 'time']






# # ✅ Handle GPT result and prompt for missing fields
# def fill_missing_fields(gpt_result):
#     if gpt_result.get("intent") != "schedule_meeting":
#         return gpt_result

#     # Extract fields
#     title = gpt_result.get("title", "").strip()
#     date_str = gpt_result.get("date", "").strip()
#     time_str = gpt_result.get("time", "").strip()

#     if not title:
#         gpt_result["title"] = ask_for_field("title")

#     if not is_valid_date(date_str):
#         gpt_result["date"] = ask_for_field("date")

#     if not is_valid_time(time_str):
#         gpt_result["time"] = ask_for_field("time")

#     return gpt_result


# # ✅ Orchestrator for scheduling
# def handle_scheduling(gpt_result):
#     result = intelligent_schedule_handler(gpt_result)

#     if result['status'] == 'scheduled':
#         speak_text(f"✅ Your meeting has been scheduled from {result['start']} to {result['end']}.")
#     elif result['status'] == 'conflict':
#         speak_text("⚠️ There's a conflict with your calendar.")
#         speak_text(f"Would you prefer {result['suggested_start']} instead?")
#     elif result['status'] == 'missing_info':
#         speak_text(result['message'])
#     else:
#         speak_text("❌ Something went wrong while scheduling. Please try again.")


# # ✅ Main Loop
# def main():
#     print("🎤 Voice Assistant is ready. Say something to schedule a meeting!")

#     while True:
#         user_input = listen_and_transcribe().strip().lower()

#         if not user_input:
#             speak_text("Sorry, I didn't catch that. Could you please repeat?")
#             continue

#         print("👤 You said:", user_input)

#         if any(cmd in user_input for cmd in EXIT_COMMANDS):
#             # speak_text("Are you sure you want to exit?")
#             # confirmation = listen_and_transcribe().strip().lower()
#             if any(cmd in user_input for cmd in EXIT_COMMANDS):
#                 goodbye = "Thanks for using the voice assistant. Have a great day!"
#                 print("👋 Exiting: " + goodbye)
#                 speak_text(goodbye)
#                 break
#             else:
#                 continue  # User changed their mind

#         gpt_result = run_gpt_agent(user_input)
#         print("🤖 GPT Result:", gpt_result)

#         response_text = gpt_result.get("reply")
#         if response_text:
#             speak_text(response_text)
#         else:
#             speak_text("Got it. Let me handle that.")

#         if gpt_result.get("intent") == "schedule_meeting":
#             gpt_result = fill_missing_fields(gpt_result)
#             handle_scheduling(gpt_result)


# if __name__ == "__main__":
#     main()
