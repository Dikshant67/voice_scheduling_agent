import azure.cognitiveservices.speech as speechsdk
import logging
from config.config import Config

class TextToVoice:
    def __init__(self, speech_key: str, speech_region: str):
        if not speech_key or not speech_region:
            raise Exception("Azure Speech key or region not set in environment variables.")
        self.speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
        self.speech_config.speech_synthesis_voice_name = "en-IN-NeerjaNeural"  # Hindi/Indian English voice
        self.logger = logging.getLogger(__name__)

    def synthesize(self, text: str) -> bytes:
        try:
            self.logger.info(f"🗣️ Synthesizing: {text}")
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config)
            result = synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                self.logger.info("✅ Speech synthesis completed.")
                return result.audio_data
            else:
                self.logger.warning(f"⚠️ Speech synthesis failed: {result.reason}")
                return b""
        except Exception as e:
            self.logger.error(f"TTS error: {str(e)}")
            return b""