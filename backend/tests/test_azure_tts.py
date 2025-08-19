import os
import azure.cognitiveservices.speech as speechsdk
import dotenv

dotenv.load_dotenv()  # Load environment variables from .env file
def test_azure_tts():
    """Test Azure Text to Speech service"""
    
    # Replace with your actual keys
    AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
    AZURE_REGION = os.getenv("AZURE_SPEECH_REGION")
    
    try:
        # Configure speech service
        speech_config = speechsdk.SpeechConfig(
            subscription=AZURE_SPEECH_KEY, 
            region=AZURE_REGION
        )
        
        # Test 1: Play audio directly
        print("🔊 Testing TTS with speaker output...")
        audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, 
            audio_config=audio_config
        )
        
        test_text = "Hello! This is a test of Azure Text to Speech service."
        result = synthesizer.speak_text_async(test_text).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print("✅ TTS SUCCESS: Audio played successfully")
        elif result.reason == speechsdk.ResultReason.Canceled:
            print(f"❌ TTS FAILED: {result.cancellation_details.reason}")
            if result.cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"Error details: {result.cancellation_details.error_details}")
            return False
        
        # Test 2: Save to file
        print("💾 Testing TTS with file output...")
        audio_config = speechsdk.audio.AudioOutputConfig(filename="test_tts_output.wav")
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, 
            audio_config=audio_config
        )
        
        result = synthesizer.speak_text_async(test_text).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print("✅ TTS SUCCESS: Audio saved to test_tts_output.wav")
            return True
        else:
            print("❌ TTS FAILED: Could not save audio file")
            return False
            
    except Exception as e:
        print(f"❌ TTS ERROR: {e}")
        return False

if __name__ == "__main__":
    test_azure_tts()
