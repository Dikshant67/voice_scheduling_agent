import azure.cognitiveservices.speech as speechsdk
import logging
from config.config import Config

class VoiceToText:
    def __init__(self, speech_key: str, speech_region: str):
        if not speech_key or not speech_region:
            raise Exception("Azure Speech key or region not set in environment variables.")
        self.speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
        self.speech_config.speech_recognition_language = "en-US"
        self.logger = logging.getLogger(__name__)

    def recognize(self, audio_data: bytes) -> str:
        try:
            # Create an audio stream from bytes
            audio_input = speechsdk.audio.AudioConfig(stream=speechsdk.audio.PushAudioInputStream())
            recognizer = speechsdk.SpeechRecognizer(speech_config=self.speech_config, audio_config=audio_input)
            stream = speechsdk.audio.PushAudioInputStream()
            stream.write(audio_data)
            stream.close()
            
            self.logger.info("🎙️ Processing audio data...")
            result = recognizer.recognize_once()
            
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                self.logger.info(f"📝 Recognized: {result.text}")
                return result.text
            elif result.reason == speechsdk.ResultReason.NoMatch:
                self.logger.warning("⚠️ No speech could be recognized.")
                return "I didn't catch that. Could you say it again?"
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                self.logger.error(f"❌ Speech Recognition canceled: {cancellation.reason}")
                if cancellation.reason == speechsdk.CancellationReason.Error:
                    self.logger.error(f"🔍 Error details: {cancellation.error_details}")
                return "There was an error with speech recognition."
        except Exception as e:
            self.logger.error(f"STT error: {str(e)}")
            return f"Error processing audio: {str(e)}"