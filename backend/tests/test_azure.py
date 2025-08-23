# In test_azure.py

import os
import sys
import logging
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

# --- SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. LOAD ENVIRONMENT VARIABLES ---
# This loads the keys from your .env file
load_dotenv() 

# Get credentials from environment
azure_speech_key = os.getenv("AZURE_SPEECH_KEY")
azure_speech_region = os.getenv("AZURE_SPEECH_REGION")

def test_transcription(file_path: str):
    """
    A simple, direct test of the Azure Speech to Text service.
    """
    logging.info("--- Starting Azure STT Test ---")

    # --- 2. VERIFY CREDENTIALS ---
    if not azure_speech_key or not azure_speech_region:
        logging.error("FATAL ERROR: AZURE_SPEECH_KEY or AZURE_SPEECH_REGION not found in .env file.")
        return

    # Print the loaded keys (partially hidden for security) to confirm they are correct
    logging.info(f"Using Azure Region: {azure_speech_region}")
    logging.info(f"Using Azure Key: ...{azure_speech_key[-4:]}") # Shows only the last 4 characters

    # --- 3. CONFIGURE AND RUN AZURE SDK ---
    try:
        speech_config = speechsdk.SpeechConfig(subscription=azure_speech_key, region=azure_speech_region)
        speech_config.speech_recognition_language = "en-US"
        
        audio_config = speechsdk.audio.AudioConfig(filename=file_path)
        
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        
        logging.info(f"Attempting to recognize speech from: {file_path}")
        result = recognizer.recognize_once_async().get()

        # --- 4. ANALYZE RESULT ---
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            logging.info("✅ SUCCESS!")
            logging.info(f"Recognized Text: '{result.text}'")
        elif result.reason == speechsdk.ResultReason.NoMatch:
            logging.warning("⚠️ FAILURE: No speech could be recognized.")
            logging.warning("This could mean the audio was silent or the microphone volume was too low.")
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            logging.error(f"❌ FAILURE: Speech recognition was canceled. Reason: {cancellation.reason}")
            if cancellation.reason == speechsdk.CancellationReason.Error:
                logging.error(f"🔥 CRITICAL ERROR DETAILS: {cancellation.error_details}")
                logging.error("This often means your API key is invalid or your network is blocking Azure.")

    except Exception as e:
        logging.error(f"💥 An unexpected exception occurred: {e}", exc_info=True)

    logging.info("--- Test Complete ---")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_azure.py \"./tests\"")
    else:
        test_file_path = sys.argv[1]
        test_transcription(test_file_path)