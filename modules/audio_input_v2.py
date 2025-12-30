#!/usr/bin/env python3
"""
Audio Input Module V2 - Single stream architecture
Uses ONE continuous audio stream with dual processors (wake word + transcription)
Eliminates buffer echo issues from repeatedly opening/closing streams
"""

from openwakeword.model import Model
from faster_whisper import WhisperModel
import paho.mqtt.client as mqtt
import sounddevice as sd
import numpy as np
from scipy import signal as scipy_signal
import yaml
import time
from datetime import datetime
import io
import wave
from collections import deque
from threading import Lock

def ts():
    """Get timestamp string for logging"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

# Audio device configuration
MIC_INDEX = None  # Use system default device

class AudioInput:
    def __init__(self):
        # Load config
        with open('config/mqtt.yaml', 'r') as f:
            mqtt_config = yaml.safe_load(f)
        with open('config/session.yaml', 'r') as f:
            session_config = yaml.safe_load(f)
        
        self.topics = mqtt_config['topics']
        self.wake_threshold = session_config['session']['wake_word_threshold']
        
        # Audio settings
        self.mic_rate = 48000  # Mic native rate
        self.whisper_rate = 16000  # Whisper needs 16kHz
        self.chunk_samples = 2000  # ~42ms chunks for wake word
        
        # State
        self.session_state = "idle"
        self.robot_speaking = False
        self.last_wake_detection_time = 0  # Cooldown timer
        self.wake_cooldown_seconds = 3.0  # Don't re-detect for 3s after wake word
        self.last_detection_attempt = 0  # Rate limiting - prevent rapid-fire detections
        self.detection_rate_limit = 2.0  # Minimum 2 seconds between detection attempts
        
        # Ring buffer for transcription - stores last N seconds of audio
        self.buffer_duration = 10  # Keep 10 seconds
        self.buffer_samples = self.mic_rate * self.buffer_duration
        self.audio_buffer = deque(maxlen=self.buffer_samples)
        self.buffer_lock = Lock()
        
        # Recording state for transcription mode
        self.recording = False
        self.recording_buffer = []
        self.silence_start = None
        
        # VAD settings
        self.SILENCE_THRESHOLD = 300
        self.SILENCE_DURATION = 2.5  # seconds
        self.MAX_RECORDING = 30  # seconds
        
        # Models
        print("[AudioInput] Loading wake word detector...")
        self.oww = Model()
        print(f"[AudioInput] ✓ Wake word models: {list(self.oww.models.keys())}")
        print(f"[AudioInput] Wake word threshold: {self.wake_threshold}")
        
        print("[AudioInput] Loading Whisper...")
        self.whisper = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("[AudioInput] ✓ Whisper ready")
        
        # MQTT
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="audio_input")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        # Single continuous stream - created once, never closed
        self.stream = None
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"[AudioInput] Connected to MQTT broker (rc={rc})")
        client.subscribe(self.topics['session']['state'])
        client.subscribe(self.topics['robot']['speaking'])
    
    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        if topic == self.topics['session']['state']:
            old_state = self.session_state
            self.session_state = payload
            
            # Start recording when transitioning to ACTIVE
            if old_state == "idle" and payload == "active":
                print("[AudioInput] 🎧 Starting transcription recording...")
                self.start_recording()
                    
        elif topic == self.topics['robot']['speaking']:
            self.robot_speaking = (payload == "true")
    
    def audio_callback(self, indata, frames, time_info, status):
        """
        Continuous audio callback - processes EVERY audio chunk
        Handles both wake word detection AND transcription recording
        """
        if status:
            print(f"[AudioInput] Stream status: {status}")
        
        # Convert to int16 numpy array
        audio_chunk = indata[:, 0].copy()  # Get first channel
        
        # Add to ring buffer (for potential future use)
        with self.buffer_lock:
            self.audio_buffer.extend(audio_chunk)
        
        # MODE 1: Wake word detection (when IDLE and not speaking)
        if self.session_state == "idle" and not self.robot_speaking:
            self.process_wake_word(audio_chunk)
        
        # MODE 2: Recording for transcription (when ACTIVE)
        elif self.session_state == "active" and self.recording:
            self.process_recording(audio_chunk)
    
    def process_wake_word(self, audio_chunk):
        """Process audio for wake word detection - EXACT working pattern from test_wakeword.py"""
        # CRITICAL: Defensive check - NEVER process wake word if recording or not in IDLE state
        if self.session_state != "idle" or self.recording:
            return  # Absolutely NO wake word detection during recording
        
        # Audio chunk is EXACTLY chunk_samples (2000 @ 48kHz) because blocksize matches
        audio_48k = audio_chunk
        
        # Check audio volume first
        volume = int(np.abs(audio_48k).mean())
        
        # CRITICAL: Skip if volume too low - prevents false positives from ambient noise
        # If it's too quiet to record speech, it's too quiet to contain a wake word
        if volume < self.SILENCE_THRESHOLD:
            return  # Skip silent/near-silent audio
        
        # Rate limiting - prevent rapid-fire detections (max 1 detection per 2 seconds)
        time_since_last_attempt = time.time() - self.last_detection_attempt
        if self.last_detection_attempt > 0 and time_since_last_attempt < self.detection_rate_limit:
            return  # Skip - too soon since last detection attempt
        
        # Cooldown check - prevent detecting echoes/buffer remnants
        time_since_last_wake = time.time() - self.last_wake_detection_time
        if self.last_wake_detection_time > 0 and time_since_last_wake < self.wake_cooldown_seconds:
            return  # Skip processing during cooldown
        
        # CRITICAL: Decimate 48kHz -> 16kHz using EXACT working method
        # Use trim_len method - this preserves temporal alignment for the model
        # Results in ~666 samples @ 16kHz which is what the model expects for proper timing
        trim_len = (len(audio_48k) // 3) * 3
        audio_16k = audio_48k[:trim_len].reshape(-1, 3).mean(axis=1).astype(np.int16)
        
        # Detect wake word
        prediction = self.oww.predict(audio_16k)
        
        # Show scores when there's audio activity (reduced spam)
        jarvis_score = prediction.get('hey_jarvis', 0.0)
        if jarvis_score > 0.1:  # Only show significant scores to reduce spam
            print(f"[{ts()}] [vol: {volume:5d}] hey_jarvis: {jarvis_score:.3f} (threshold: {self.wake_threshold})")
        
        # Check for detection
        if 'hey_jarvis' in prediction:
            jarvis_score = prediction['hey_jarvis']
            if jarvis_score > self.wake_threshold:
                # Record this detection attempt time for rate limiting
                self.last_detection_attempt = time.time()
                
                print(f"\n[{ts()}] [AudioInput] 🔊 Wake word detected! (score: {jarvis_score:.2f}, volume: {volume})")
                self.client.publish(self.topics['session']['wake_detected'], f"{jarvis_score}")
                
                # CRITICAL: Reset model's internal buffer to prevent score persistence
                # This clears the sliding window so we don't re-detect the same pattern
                self.oww.reset()
                print(f"[{ts()}] [AudioInput] 🔄 Model buffer reset")
                
                # STANDALONE MODE: Auto-transition to ACTIVE
                print(f"[{ts()}] [AudioInput] [STANDALONE] Auto-transitioning to ACTIVE state...")
                self.session_state = "active"
                self.start_recording()
                time.sleep(0.3)  # Brief pause before recording
    
    def start_recording(self):
        """Start recording for transcription"""
        self.recording = True
        self.recording_buffer = []
        self.silence_start = None
        self.recording_start_time = time.time()
        print(f"[{ts()}] [AudioInput] 🎙️ Recording started (VAD-based)...")
    
    def process_recording(self, audio_chunk):
        """Process audio chunk during recording mode"""
        if not self.recording:
            return
        
        # Add to recording buffer
        self.recording_buffer.append(audio_chunk.copy())
        
        # Check for silence (VAD)
        volume = np.abs(audio_chunk).mean()
        
        if volume > self.SILENCE_THRESHOLD:
            # Audio detected - reset silence timer
            self.silence_start = None
            print("🗣️", end='', flush=True)
        else:
            # Silence detected
            if self.silence_start is None:
                self.silence_start = time.time()
            print(".", end='', flush=True)
            
            # Check if silence duration exceeded
            silence_duration = time.time() - self.silence_start
            if silence_duration >= self.SILENCE_DURATION:
                print()
                self.stop_recording_and_transcribe("silence")
                return
        
        # Check max recording time
        recording_duration = time.time() - self.recording_start_time
        if recording_duration >= self.MAX_RECORDING:
            print()
            self.stop_recording_and_transcribe("max_time")
    
    def stop_recording_and_transcribe(self, reason):
        """Stop recording and transcribe the audio"""
        self.recording = False
        
        duration = time.time() - self.recording_start_time
        print(f"\n[{ts()}] [AudioInput] ✓ Recording stopped ({reason}): {duration:.1f}s")
        
        # Convert recording buffer to audio array
        if not self.recording_buffer:
            print(f"[{ts()}] [AudioInput] ❌ No audio recorded")
            self.session_state = "idle"
            return
        
        audio_48k = np.concatenate(self.recording_buffer)
        
        # Resample to 16kHz for Whisper
        audio_16k = scipy_signal.resample_poly(audio_48k, self.whisper_rate, self.mic_rate)
        audio_16k = audio_16k.astype(np.float32) / 32768.0  # Normalize to [-1, 1]
        
        # Transcribe
        print(f"[{ts()}] [AudioInput] ⚡ Transcribing...")
        start = time.time()
        
        segments, info = self.whisper.transcribe(audio_16k, beam_size=1, language="en", vad_filter=True)
        text_parts = [seg.text.strip() for seg in segments]
        text = " ".join(text_parts).strip()
        
        elapsed = time.time() - start
        
        if text:
            print(f"[{ts()}] [AudioInput] ✅ '{text}' ({elapsed:.2f}s)")
            self.client.publish(self.topics['audio']['transcription'], text)
        else:
            print(f"[{ts()}] [AudioInput] ❌ No speech detected ({elapsed:.2f}s)")
        
        # STANDALONE MODE: Return to IDLE
        print(f"[{ts()}] [AudioInput] [STANDALONE] Returning to IDLE for wake word detection...")
        self.session_state = "idle"
        
        # CRITICAL: Reset model buffer when returning to IDLE to prevent echoes
        self.oww.reset()
        print(f"[{ts()}] [AudioInput] 🔄 Model buffer reset for fresh wake word detection")
        
        # CRITICAL: Start cooldown timer NOW to prevent detecting buffer echoes
        self.last_wake_detection_time = time.time()
        cooldown_until = datetime.fromtimestamp(self.last_wake_detection_time + self.wake_cooldown_seconds).strftime("%H:%M:%S")
        print(f"[{ts()}] [AudioInput] 🔒 Wake word cooldown active until {cooldown_until} ({self.wake_cooldown_seconds}s)")
        # No wake_chunk_buffer to clear - we process chunks directly now
    
    def start(self):
        """Start audio input with single continuous stream"""
        print("[AudioInput] Starting...")
        
        # Connect MQTT
        with open('config/mqtt.yaml', 'r') as f:
            mqtt_config = yaml.safe_load(f)
        broker = mqtt_config['mqtt']['broker']
        port = mqtt_config['mqtt']['port']
        
        self.client.connect(broker, port, 60)
        self.client.loop_start()
        
        print("[AudioInput] 🎤 Opening continuous audio stream...")
        
        # Create SINGLE continuous stream - never closed!
        # CRITICAL: blocksize MUST match chunk_samples for wake word timing accuracy
        self.stream = sd.InputStream(
            device=MIC_INDEX,
            samplerate=self.mic_rate,
            dtype='int16',
            channels=1,
            blocksize=self.chunk_samples,  # 2000 samples = 41.7ms (wake word timing requirement)
            callback=self.audio_callback
        )
        
        print("[AudioInput] ✓ Stream started. Listening for wake word...")
        self.stream.start()
        
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[AudioInput] Stopping...")
            self.stream.stop()
            self.stream.close()
            self.client.loop_stop()
            self.client.disconnect()

if __name__ == "__main__":
    audio = AudioInput()
    audio.start()
