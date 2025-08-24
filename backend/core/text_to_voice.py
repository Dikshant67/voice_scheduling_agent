import azure.cognitiveservices.speech as speechsdk
import logging
from config.config import Config

class TextToVoice:
    def __init__(self, speech_key: str, speech_region: str):
        if not speech_key or not speech_region:
            raise Exception("Azure Speech key or region not set in environment variables.")
        
        self.speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
        self.speech_config.speech_synthesis_voice_name = "en-IN-NeerjaNeural"
        
        # Set audio format to WAV for frontend compatibility
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
        )   
        self.logger = logging.getLogger(__name__)

    def synthesize(self, text: str) -> bytes:
        try:
            if not text or not text.strip():
                self.logger.warning("⚠️ Empty text provided for synthesis")
                return b""
            
            self.logger.info(f"🗣️ Synthesizing: {text}")
            
            # Create synthesizer with explicit audio config for better control
            # audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config, 
                audio_config=None
            )
            
            result = synthesizer.speak_text_async(text).get()
            synthesizer.stop_speaking_async().get()  # Ensure we stop any ongoing speech
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                self.logger.info(f"✅ Speech synthesis completed. Audio size: {len(result.audio_data)} bytes")
                return result.audio_data
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                self.logger.error(f"❌ Speech synthesis canceled: {cancellation.reason}")
                if cancellation.reason == speechsdk.CancellationReason.Error:
                    self.logger.error(f"🔍 Error details: {cancellation.error_details}")
                return b""
            else:
                self.logger.warning(f"⚠️ Speech synthesis failed: {result.reason}")
                return b""
                
        except Exception as e:
            self.logger.error(f"TTS error: {str(e)}")
            return b""

    def synthesize_to_file(self, text: str, filename: str) -> bool:
        """Optional: Save synthesized audio to file for testing"""
        try:
            audio_config = speechsdk.audio.AudioOutputConfig(filename=filename)
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config, 
                audio_config=audio_config
            )
            
            result = synthesizer.speak_text_async(text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                self.logger.info(f"✅ Audio saved to {filename}")
                return True
            else:
                self.logger.error(f"❌ Failed to save audio: {result.reason}")
                return False
                
        except Exception as e:
            self.logger.error(f"File synthesis error: {str(e)}")
            return False