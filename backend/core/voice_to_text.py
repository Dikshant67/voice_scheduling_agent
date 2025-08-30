# In core/voice_to_text.py

import asyncio
import os
import wave
import logging
import azure.cognitiveservices.speech as speechsdk
import numpy as np
from config.config import Config



# Get a logger instance for this module
logger = logging.getLogger(__name__)

def validate_wav_quality(wav_path: str) -> dict:
    """
    Analyzes a WAV file to ensure it meets quality standards before sending to the STT service.
    This prevents wasting API calls on silent or corrupt audio.
    """
    try:
        with wave.open(wav_path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            sample_rate = wav_file.getframerate()
            duration = frames / sample_rate
            
            # Check for common issues - lenient for short commands like "option 1"
            if duration < 0.1:  # Allow even shorter clips for brief selections
                return {'is_valid': False, 'reason': 'Audio is too short'}
            
            # Allow common sample rates (Azure STT can handle various rates)
            allowed_rates = [8000, 16000, 22050, 44100, 48000]
            if sample_rate not in allowed_rates:
                logger.warning(f"Unusual sample rate: {sample_rate}Hz, but proceeding with STT")
            
            return {'is_valid': True, 'duration': duration, 'sample_rate': sample_rate}
            
    except Exception as e:
        logger.warning(f"Could not validate WAV file quality: {e}")
        return {'is_valid': False, 'reason': f'File validation failed: {str(e)}'}


async def stt_from_pcm(pcm_bytes: bytes, sample_rate: int = 16000) -> str:
    try:
        if not pcm_bytes:
            return ""
        config = Config()
        speech_config = speechsdk.SpeechConfig(
            subscription=config.azure_speech_key,
            region=config.azure_speech_region
        )
        speech_config.speech_recognition_language = "en-US"
        # Faster endpointing
        speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs, "2000"
        )
        speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "500"
        )

        fmt = speechsdk.audio.AudioStreamFormat(
            samples_per_second=sample_rate,
            bits_per_sample=16,
            channels=1
        )
        push = speechsdk.audio.PushAudioInputStream(fmt)
        push.write(pcm_bytes)
        push.close()

        audio_cfg = speechsdk.audio.AudioConfig(stream=push)
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_cfg)

        future = recognizer.recognize_once_async()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, future.get)

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return result.text.strip()
        return ""
    except Exception as e:
        logger.error(f"STT memory error: {e}", exc_info=True)
        return ""

async def enhanced_speech_to_text(file_path: str) -> str:
    """
    Performs Speech-to-Text on a given audio file path using Azure's Speech SDK.
    
    This function is asynchronous (`async`) to avoid blocking the main server thread.
    It's more efficient than the old class-based, in-memory stream approach.
    """
    try:
        logger.info(f"🎙️ Starting STT processing for {os.path.basename(file_path)}")
        
        # 1. Validate Audio Quality First
        quality = validate_wav_quality(file_path)
        if not quality['is_valid']:
            logger.warning(f"Skipping STT due to poor audio quality: {quality['reason']}")
            return ""
        else:
            logger.info(f"✅ Audio quality validated: {quality.get('duration', 'N/A')}s duration, {quality.get('sample_rate', 'N/A')}Hz")

        # 2. Load configuration to get API keys safely
        config = Config()
        
        speech_config = speechsdk.SpeechConfig(
            subscription=config.azure_speech_key,
            region=config.azure_speech_region
        )
        speech_config.speech_recognition_language = "en-US"
        
        # Add more robust configuration
        speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs, "5000")
        speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "1000")
        
        # 3. Use the more reliable file-based AudioConfig
        # The Azure SDK is highly optimized for this.
        audio_config = speechsdk.audio.AudioConfig(filename=file_path)
        
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, 
            audio_config=audio_config
        )
        
        
         
        # 1. Get the 'Future' object from the SDK
        future = speech_recognizer.recognize_once_async()
        
        # 2. Run the blocking '.get()' method in a separate thread to avoid freezing the server
        loop = asyncio.get_running_loop()
        
        result = await loop.run_in_executor(None, future.get)
      
    
        # 5. Process the result
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            transcribed_text = result.text.strip()
            logger.info(f"✅ STT Success: '{transcribed_text}' (confidence: {getattr(result, 'confidence', 'N/A')})")
            return transcribed_text
        elif result.reason == speechsdk.ResultReason.NoMatch:
            logger.warning(f"⚠️ No speech could be recognized from the audio. File: {os.path.basename(file_path)}")
            logger.info(f"🔍 Audio details: {quality}")
            logger.info(f"🔍 No match details: {result.no_match_details if hasattr(result, 'no_match_details') else 'N/A'}")
            return ""
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            logger.error(f"❌ Speech recognition was canceled: {cancellation.reason}")
            if cancellation.reason == speechsdk.CancellationReason.Error:
                logger.error(f"🔍 Error details: {cancellation.error_details}")
                logger.error(f"🔍 Audio file: {os.path.basename(file_path)}, Details: {quality}")
            return ""
            
    except Exception as e:
        logger.error(f"💥 An unexpected error occurred during STT: {e}", exc_info=True)
        return ""
    
    return ""