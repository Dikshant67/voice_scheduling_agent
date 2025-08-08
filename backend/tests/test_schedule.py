from calendar_service import intelligent_schedule_handler
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

gpt_output = {
    'intent': 'schedule_meeting',
    'title': 'Team Sync',
    'date': '2025-08-16',
    'time': '11:00'
}

result = intelligent_schedule_handler(gpt_output)
print("🧠 AI Response:", result)
