import azure.cognitiveservices.speech as speechsdk
import io
import logging
from pydub import AudioSegment
import tempfile

class VoiceToText:
    def __init__(self, speech_key: str, speech_region: str):
        if not speech_key or not speech_region:
            raise Exception("Azure Speech key or region not set in environment variables.")
        self.speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
        self.speech_config.speech_recognition_language = "en-US"
        self.logger = logging.getLogger(__name__)

    def recognize(self, audio_data: bytes) -> str:
        try:
            self.logger.info(f"Processing {len(audio_data)} bytes of audio data...")
            
            # Debug: Check audio format
            self.logger.info(f"Audio header: {audio_data[:20].hex()}")
            
            # Convert WebM/OGG to WAV format that Azure STT can handle
            try:
                # Use pydub to convert audio format
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
                
                # Convert to the format Azure STT expects
                audio_segment = audio_segment.set_frame_rate(16000)  # 16kHz
                audio_segment = audio_segment.set_channels(1)       # Mono
                audio_segment = audio_segment.set_sample_width(2)   # 16-bit
                
                # Export to WAV format in memory
                wav_io = io.BytesIO()
                audio_segment.export(wav_io, format="wav")
                wav_data = wav_io.getvalue()
                wav_io.close()
                
                self.logger.info(f"Converted to WAV: {len(wav_data)} bytes")
                
            except Exception as conversion_error:
                self.logger.error(f"Audio conversion failed: {str(conversion_error)}")
                # Fallback: try using original data
                wav_data = audio_data
            
            # Create audio stream with proper format
            audio_format = speechsdk.audio.AudioStreamFormat(
                samples_per_second=16000,
                bits_per_sample=16,
                channels=1
            )
            
            # Create push stream with the converted audio
            audio_stream = speechsdk.audio.PushAudioInputStream(audio_format)
            audio_config = speechsdk.audio.AudioConfig(stream=audio_stream)
            
            # Create recognizer
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config, 
                audio_config=audio_config
            )
            
            # Write converted audio data to stream
            audio_stream.write(wav_data)
            audio_stream.close()
            
            self.logger.info("Performing speech recognition...")
            result = recognizer.recognize_once()
            
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                self.logger.info(f"Recognized: {result.text}")
                return result.text
            elif result.reason == speechsdk.ResultReason.NoMatch:
                self.logger.warning("No speech could be recognized.")
                return ""
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                self.logger.error(f"Speech Recognition canceled: {cancellation.reason}")
                if cancellation.reason == speechsdk.CancellationReason.Error:
                    self.logger.error(f"Error details: {cancellation.error_details}")
                    # Try alternative recognition method
                    return self._fallback_recognition(audio_data)
                return ""
                
        except Exception as e:
            self.logger.error(f"STT error: {str(e)}")
            return ""

    def _fallback_recognition(self, audio_data: bytes) -> str:
        """Fallback method using different approach"""
        try:
            self.logger.info("Trying fallback recognition method...")
            
            # Save to temporary file and use file-based recognition
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                # Convert to WAV and save
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
                audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
                audio_segment.export(temp_file.name, format="wav")
                
                # Use file-based recognition
                audio_config = speechsdk.audio.AudioConfig(filename=temp_file.name)
                recognizer = speechsdk.SpeechRecognizer(
                    speech_config=self.speech_config, 
                    audio_config=audio_config
                )
                
                result = recognizer.recognize_once()
                
                # Clean up temp file
                import os
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
                
                if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    self.logger.info(f"Fallback recognition successful: {result.text}")
                    return result.text
                else:
                    self.logger.warning("Fallback recognition also failed")
                    return ""
                    
        except Exception as e:
            self.logger.error(f"Fallback recognition error: {str(e)}")
            return ""