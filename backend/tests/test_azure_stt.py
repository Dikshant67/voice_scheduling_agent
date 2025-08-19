import os
import azure.cognitiveservices.speech as speechsdk
import dotenv

dotenv.load_dotenv()  # Load environment variables from .env file
def test_azure_stt():
    """Test Azure Speech to Text service"""
    
       # Replace with your actual keys
    AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
    AZURE_REGION = os.getenv("AZURE_SPEECH_REGION")
    
    try:
        # Configure speech service
        speech_config = speechsdk.SpeechConfig(
            subscription=AZURE_SPEECH_KEY, 
            region=AZURE_REGION
        )
        speech_config.speech_recognition_language = "en-US"
        
        # Test with microphone input
        print("🎤 Testing STT with microphone...")
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, 
            audio_config=audio_config
        )
        
        print("Please speak something...")
        result = recognizer.recognize_once()
        
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            print(f"✅ STT SUCCESS: '{result.text}'")
            return True
        elif result.reason == speechsdk.ResultReason.NoMatch:
            print("❌ STT FAILED: No speech recognized")
        elif result.reason == speechsdk.ResultReason.Canceled:
            print(f"❌ STT FAILED: {result.cancellation_details.reason}")
            if result.cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"Error details: {result.cancellation_details.error_details}")
        
        return False
        
    except Exception as e:
        print(f"❌ STT ERROR: {e}")
        return False

if __name__ == "__main__":
    test_azure_stt()
