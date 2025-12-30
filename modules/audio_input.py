#!/usr/bin/env python3
"""
Audio Input Module - Wake word detection + Speech-to-text
Publishes to MQTT when wake word detected or speech transcribed
"""

from openwakeword.model import Model
from faster_whisper import WhisperModel
import paho.mqtt.client as mqtt
import sounddevice as sd
import numpy as np
from scipy import signal
import yaml
import time

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
        # Mic supports: 44.1kHz, 48kHz only (tested)
        self.mic_rate = 48000  # Use 48kHz (works for wake word decimation)
        self.whisper_rate = 16000  # Whisper needs 16kHz
        self.chunk_samples = 2000  # For wake word detection
        self.transcribe_duration = 3  # seconds
        
        # State
        self.session_state = "idle"
        self.robot_speaking = False
        
        # Models
        print("[AudioInput] Loading wake word detector...")
        self.oww = Model()
        available_models = list(self.oww.models.keys())
        print(f"[AudioInput] ✓ Available models: {available_models}")
        
        # Use hey_jarvis model
        if 'hey_jarvis' not in available_models:
            print("[AudioInput] ERROR: hey_jarvis model NOT found!")
            print("[AudioInput] Download with: openwakeword-cli --download_model hey_jarvis")
        else:
            print("[AudioInput] ✓ hey_jarvis wake word model loaded")
        
        print(f"[AudioInput] Wake word threshold: {self.wake_threshold}")
        
        print("[AudioInput] Loading Whisper...")
        self.whisper = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("[AudioInput] ✓ Whisper ready")
        
        # Audio stream will be managed in run loop
        self.wake_stream = None
        
        # MQTT
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="audio_input")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"[AudioInput] Connected to MQTT broker (rc={rc})")
        
        # Subscribe to session state and robot speaking
        client.subscribe(self.topics['session']['state'])
        client.subscribe(self.topics['robot']['speaking'])
    
    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        if topic == self.topics['session']['state']:
            old_state = self.session_state
            self.session_state = payload
            
            # When returning to IDLE, flush wake word stream to clear old audio
            if old_state != "idle" and payload == "idle":
                print("[AudioInput] 🔄 Session ended, flushing audio buffer...")
                if self.wake_stream is not None:
                    self.wake_stream.stop()
                    self.wake_stream.close()
                    self.wake_stream = None
                    # Will be reopened on next listen_wake_word() call
                    
        elif topic == self.topics['robot']['speaking']:
            self.robot_speaking = (payload == "true")
    
    def listen_wake_word(self):
        """Single iteration of wake word detection"""
        # Skip if robot is speaking
        if self.robot_speaking:
            return
        
        # Ensure wake word stream is open
        if self.wake_stream is None:
            self.wake_stream = sd.InputStream(
                device=MIC_INDEX,
                samplerate=self.mic_rate,
                dtype='int16',
                channels=1,
                blocksize=self.chunk_samples  # CRITICAL: Use 2000 samples @ 48kHz
            )
            self.wake_stream.start()
            
            # CRITICAL: Flush buffered audio to prevent echo detections
            # Discard any audio that was buffered during transcription/processing
            print("[AudioInput] 🔄 Flushing wake stream buffer to prevent echo...")
            time.sleep(0.1)  # Let buffer populate
            while True:
                readable = self.wake_stream.read_available
                if readable > 0:
                    self.wake_stream.read(readable)  # Discard buffered data
                else:
                    break
            print("[AudioInput] ✓ Buffer flushed, ready for wake word")
        
        # Read audio chunk from stream (EXACT method from working test_wakeword.py)
        # CRITICAL: Read exactly self.chunk_samples (2000 @ 48kHz)
        indata, overflowed = self.wake_stream.read(self.chunk_samples)
        
        # Convert to numpy array
        audio_48k = np.frombuffer(indata, dtype=np.int16)
        
        # Check audio level
        vol = np.abs(audio_48k).mean()
        
        # Decimate by 3: 48kHz -> 16kHz (EXACT method from working test_wakeword.py)
        # CRITICAL: Use trim_len method - this preserves temporal alignment
        # Results in ~666 samples @ 16kHz which is what the model expects
        trim_len = (len(audio_48k) // 3) * 3
        audio_16k = audio_48k[:trim_len].reshape(-1, 3).mean(axis=1).astype(np.int16)
        
        # Detect wake word
        prediction = self.oww.predict(audio_16k)
        
        # Show scores when there's audio activity
        if vol > 100:
            jarvis_score = prediction.get('hey_jarvis', 0.0)
            if jarvis_score > 0.05:  # Show any meaningful score
                print(f"[vol: {int(vol):5d}] hey_jarvis: {jarvis_score:.3f} (threshold: {self.wake_threshold})")
        
        # Wake word detected in IDLE state
        if self.session_state == "idle" and 'hey_jarvis' in prediction:
            jarvis_score = prediction['hey_jarvis']
            
            if jarvis_score > self.wake_threshold:
                print(f"\n[AudioInput] 🔊 Wake word 'Hey Jarvis' detected! (score: {jarvis_score:.2f})")
                self.client.publish(self.topics['session']['wake_detected'], f"{jarvis_score}")
                
                # STANDALONE MODE: Auto-transition to active for testing
                print("[AudioInput] [STANDALONE] Auto-transitioning to ACTIVE state...")
                self.session_state = "active"
                
                # Wait a moment before starting transcription
                time.sleep(0.5)
    
    def listen_and_transcribe(self, duration=None):
        """Record audio with Voice Activity Detection and transcribe"""
        # Close wake word stream to free device
        if self.wake_stream is not None:
            self.wake_stream.stop()
            self.wake_stream.close()
            self.wake_stream = None
        
        print(f"[AudioInput] 🎧 Listening (VAD-based, will stop on silence)...")
        
        # VAD settings
        CHUNK_DURATION = 0.5  # 500ms chunks
        SILENCE_THRESHOLD = 500  # Audio level threshold (int16) - balanced for speech detection
        SILENCE_DURATION = 2.5  # Stop after 2.5s of silence (increased from 1.5s to avoid cutting off speech)
        MAX_RECORDING = 30  # Max 30 seconds total
        
        chunk_samples = int(CHUNK_DURATION * self.mic_rate)
        silence_chunks_needed = int(SILENCE_DURATION / CHUNK_DURATION)
        max_chunks = int(MAX_RECORDING / CHUNK_DURATION)
        
        # Open stream for VAD-based recording
        stream = sd.InputStream(
            device=MIC_INDEX,
            samplerate=self.mic_rate,
            dtype='int16',
            channels=1,
            blocksize=chunk_samples
        )
        stream.start()
        
        recorded_chunks = []
        silence_count = 0
        total_chunks = 0
        speech_detected = False
        
        try:
            while total_chunks < max_chunks:
                # Read chunk
                chunk, overflowed = stream.read(chunk_samples)
                audio_chunk = np.frombuffer(chunk, dtype=np.int16)
                
                # Check voice activity
                volume = np.abs(audio_chunk).mean()
                
                if volume > SILENCE_THRESHOLD:
                    # Speech detected
                    silence_count = 0
                    speech_detected = True
                    print("🗣️", end='', flush=True)
                else:
                    # Silence
                    if speech_detected:
                        silence_count += 1
                        print(".", end='', flush=True)
                
                recorded_chunks.append(audio_chunk)
                total_chunks += 1
                
                # Stop if we've had enough silence after speech
                if speech_detected and silence_count >= silence_chunks_needed:
                    print()
                    print(f"[AudioInput] ✓ Stopped on silence ({total_chunks * CHUNK_DURATION:.1f}s)")
                    break
        
        finally:
            stream.stop()
            stream.close()
        
        if not speech_detected:
            print("\n[AudioInput] ❌ No speech detected")
            return None
        
        # Combine all chunks
        audio_48k = np.concatenate(recorded_chunks)
        
        # Decimate by 3: 48kHz -> 16kHz for Whisper
        trim_len = (len(audio_48k) // 3) * 3
        audio_16k = audio_48k[:trim_len].reshape(-1, 3).mean(axis=1).astype(np.float32)
        # Normalize int16 to float32 range
        audio_16k = audio_16k / 32768.0
        
        # Transcribe
        print("[AudioInput] ⚡ Transcribing...")
        start = time.time()
        segments, _ = self.whisper.transcribe(audio_16k, beam_size=5, language="en")
        
        text = " ".join([seg.text for seg in segments]).strip()
        elapsed = time.time() - start
        
        # Filter Whisper hallucinations (common false positives on silence)
        hallucinations = ["You", "you", "Thank you.", "Thanks for watching.", "Bye."]
        if text in hallucinations:
            print(f"[AudioInput] ⚠️ Filtered hallucination: '{text}' ({elapsed:.2f}s)")
            return None
        
        if text:
            print(f"[AudioInput] ✅ '{text}' ({elapsed:.2f}s)")
            self.client.publish(self.topics['audio']['transcription'], text)
        else:
            print(f"[AudioInput] ❌ No speech ({elapsed:.2f}s)")
        
        return text
    
    def start(self):
        """Start audio input module"""
        print("[AudioInput] Starting...")
        
        # Connect MQTT
        with open('config/mqtt.yaml', 'r') as f:
            mqtt_config = yaml.safe_load(f)
        broker = mqtt_config['mqtt']['broker']
        port = mqtt_config['mqtt']['port']
        
        self.client.connect(broker, port, 60)
        self.client.loop_start()
        
        print("[AudioInput] 🎤 Listening for wake word...")
        
        # Main loop
        try:
            while True:
                if self.session_state == "idle":
                    # Wake word detection mode ONLY
                    self.listen_wake_word()
                elif self.session_state == "active" and not self.robot_speaking:
                    # Transcription mode - single capture then wait
                    result = self.listen_and_transcribe()
                    if result:  # Only if we got valid speech
                        # STANDALONE MODE: print result and return to IDLE
                        print(f"[AudioInput] [STANDALONE] Got transcription, returning to IDLE...")
                        self.session_state = "idle"
                        # Flush wake word stream to clear old audio
                        if self.wake_stream is not None:
                            print("[AudioInput] 🔄 Flushing wake word stream...")
                            self.wake_stream.stop()
                            self.wake_stream.close()
                            self.wake_stream = None
                    else:
                        # No speech detected - STANDALONE MODE: return to IDLE
                        print("[AudioInput] [STANDALONE] No speech, returning to IDLE...")
                        self.session_state = "idle"
                        # Flush wake word stream
                        if self.wake_stream is not None:
                            print("[AudioInput] 🔄 Flushing wake word stream...")
                            self.wake_stream.stop()
                            self.wake_stream.close()
                            self.wake_stream = None
                        time.sleep(1.0)
                else:
                    time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("\n[AudioInput] Stopping...")
            self.client.loop_stop()
            self.client.disconnect()

if __name__ == "__main__":
    audio = AudioInput()
    audio.start()
