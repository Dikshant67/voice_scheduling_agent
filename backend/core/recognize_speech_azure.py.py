# recognize_speech_azure.py
import os
import azure.cognitiveservices.speech as speechsdk

from dotenv import load_dotenv

load_dotenv()
SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

def recognize_speech_azure():
    if not SPEECH_KEY or not SPEECH_REGION:
        raise Exception("Azure Speech key or region not set in environment variables.")

    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)

    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    print("🎙️ Listening...")

    result = recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print(f"✅ Recognized: {result.text}")
        return result.text

    elif result.reason == speechsdk.ResultReason.NoMatch:
        print("❌ No speech could be recognized.")
        return ""

    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation = result.cancellation_details
        print(f"❌ Canceled: {cancellation.reason}")
        if cancellation.reason == speechsdk.CancellationReason.Error:
            print(f"Error details: {cancellation.error_details}")
        return ""

