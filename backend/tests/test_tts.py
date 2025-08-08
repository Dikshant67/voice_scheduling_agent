import pyttsx3

try:
    engine = pyttsx3.init(driverName='sapi5')
    voices = engine.getProperty('voices')
    print("Available voices:")
    for i, voice in enumerate(voices):
        print(f"{i}: {voice.name} ({voice.id})")

    engine.setProperty('voice', voices[0].id)  # Try changing to voices[1] if needed
    engine.setProperty('rate', 150)
    engine.say("Testing text to speech on Windows using pyttsx3.")
    engine.runAndWait()
except Exception as e:
    print("TTS error:", e)
