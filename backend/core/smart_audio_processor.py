# Add the SmartAudioProcessor class right after your imports
from typing import Dict, List
# Remove this line if it exists:
# audio_processors: Dict[int, SmartAudioProcessor] = {}
import numpy as np
import time

class SmartAudioProcessor:
    def __init__(self):
        self.silence_threshold = 0.1
        self.min_silence_duration = 1.5  
        self.max_recording_duration = 30  
        self.min_speech_duration = 0.8   
        
        self.audio_buffer = []
        self.last_audio_time = time.time()
        self.recording_start_time = None
        self.silence_start_time = None
        self.speech_detected = False

    def add_audio_chunk(self, pcm_data: bytes) -> bool:
        """Add audio chunk and determine if ready to process"""
        current_time = time.time()
        
        # Convert PCM to numpy array
        audio_samples = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        rms = np.sqrt(np.mean(audio_samples ** 2))
        
        if self.recording_start_time is None:
            self.recording_start_time = current_time
        
        self.audio_buffer.append(pcm_data)
        
        if rms > self.silence_threshold:
            self.speech_detected = True
            self.silence_start_time = None
            self.last_audio_time = current_time
            print(f"🗣️ Speech detected: RMS={rms:.4f}")
            return False
        else:
            if self.silence_start_time is None:
                self.silence_start_time = current_time
            
            silence_duration = current_time - self.silence_start_time
            total_duration = current_time - self.recording_start_time
            
            print(f"🔇 Silence: {silence_duration:.1f}s, Total: {total_duration:.1f}s")
            
            should_process = (
                (self.speech_detected and silence_duration >= self.min_silence_duration) or
                (total_duration >= self.max_recording_duration) or
                (self.speech_detected and silence_duration >= 0.8 and total_duration >= 3.0)
            )
            
            if should_process and total_duration >= self.min_speech_duration:
                print(f"✅ Processing triggered: speech={self.speech_detected}, silence={silence_duration:.1f}s")
                return True
        
        return False
    
    def get_complete_audio(self) -> bytes:
        complete_audio = b''.join(self.audio_buffer)
        self.reset()
        return complete_audio
    
    def reset(self):
        self.audio_buffer = []
        self.recording_start_time = None
        self.silence_start_time = None
        self.speech_detected = False

# Add session storage for multiple connections
audio_processors: Dict[int, SmartAudioProcessor] = {}
processing_status: Dict[int, bool] = {}
