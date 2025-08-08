# ✅ Ask for missing/invalid fields
from text_to_voice import speak_text
from voice_to_text import listen_and_transcribe


def ask_for_field(field):
    prompts = {
        "title": "What should I title the meeting?",
        "date": "On which date should I schedule the meeting?",
        "time": "What time should the meeting start?"
    }
    speak_text(prompts.get(field, f"Please provide the {field}"))
    return listen_and_transcribe().strip()
