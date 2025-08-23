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
            
            # Check for common issues
            if duration < 0.5:
                return {'is_valid': False, 'reason': 'Audio is too short'}
            if sample_rate != 16000:
                return {'is_valid': False, 'reason': f'Incorrect sample rate: {sample_rate}Hz'}
            
            return {'is_valid': True, 'duration': duration}
            
    except Exception as e:
        logger.warning(f"Could not validate WAV file quality: {e}")
        return {'is_valid': False, 'reason': f'File validation failed: {str(e)}'}

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

        # 2. Load configuration to get API keys safely
        config = Config()
        
        speech_config = speechsdk.SpeechConfig(
            subscription=config.azure_speech_key,
            region=config.azure_speech_region
        )
        speech_config.speech_recognition_language = "en-US"
        
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
            logger.info(f"✅ STT Success: '{result.text}'")
            return result.text.strip()
        elif result.reason == speechsdk.ResultReason.NoMatch:
            logger.warning("⚠️ No speech could be recognized from the audio.")
            return ""
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            logger.error(f"❌ Speech recognition was canceled: {cancellation.reason}")
            if cancellation.reason == speechsdk.CancellationReason.Error:
                logger.error(f"🔍 Error details: {cancellation.error_details}")
            return ""
            
    except Exception as e:
        logger.error(f"💥 An unexpected error occurred during STT: {e}", exc_info=True)
        return ""
    
    return ""