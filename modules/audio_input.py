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
        self.mic_rate = 44100
        self.whisper_rate = 16000
        self.chunk_ms = 80
        self.chunk_samples_16k = int(self.whisper_rate * self.chunk_ms / 1000)
        self.chunk_samples_44k = int(self.mic_rate * self.chunk_ms / 1000)
        
        # State
        self.session_state = "idle"
        self.robot_speaking = False
        
        # Models
        print("[AudioInput] Loading wake word detector...")
        self.oww = Model()
        print(f"[AudioInput] ✓ Models: {list(self.oww.models.keys())}")
        
        print("[AudioInput] Loading Whisper...")
        self.whisper = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("[AudioInput] ✓ Whisper ready")
        
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
            self.session_state = payload
        elif topic == self.topics['robot']['speaking']:
            self.robot_speaking = (payload == "true")
    
    def listen_wake_word(self):
        """Continuous wake word detection"""
        while True:
            # Skip if robot is speaking
            if self.robot_speaking:
                time.sleep(0.1)
                continue
            
            # Record chunk at 44.1kHz
            chunk_44k = sd.rec(self.chunk_samples_44k, samplerate=self.mic_rate,
                              channels=1, dtype='float32', device=1)
            sd.wait()
            chunk_44k = chunk_44k.flatten()
            
            # Check audio level
            vol = np.abs(chunk_44k).mean()
            
            # Resample to 16kHz for wake word
            chunk_16k = signal.resample(chunk_44k, self.chunk_samples_16k)
            chunk_16k = (chunk_16k * 32767).astype(np.int16)
            
            # Detect wake word
            prediction = self.oww.predict(chunk_16k)
            
            # Show live scores when speaking
            if vol > 0.01:
                jarvis_score = prediction.get('hey_jarvis', 0)
                print(f"[vol: {vol:.4f} | jarvis: {jarvis_score:.3f}]", end='\r')
            
            # Wake word detected in IDLE state
            if self.session_state == "idle" and 'hey_jarvis' in prediction:
                if prediction['hey_jarvis'] > self.wake_threshold:
                    score = prediction['hey_jarvis']
                    print(f"\n[AudioInput] 🔊 Wake word! (score: {score:.2f})")
                    self.client.publish(self.topics['session']['wake_detected'], f"{score}")
                    
                    # Wait a moment for session state to change
                    time.sleep(0.5)
    
    def listen_and_transcribe(self, duration=5):
        """Record audio and transcribe (called when session is active)"""
        print(f"[AudioInput] 🎧 Listening for {duration}s...")
        
        # Record at 44.1kHz
        audio_44k = sd.rec(int(duration * self.mic_rate),
                          samplerate=self.mic_rate,
                          channels=1,
                          dtype='float32',
                          device=1)
        sd.wait()
        audio_44k = audio_44k.flatten()
        
        # Resample to 16kHz for Whisper
        num_samples = int(len(audio_44k) * self.whisper_rate / self.mic_rate)
        audio_16k = signal.resample(audio_44k, num_samples)
        
        # Transcribe
        print("[AudioInput] ⚡ Transcribing...")
        start = time.time()
        segments, _ = self.whisper.transcribe(audio_16k, beam_size=5, language="en")
        
        text = " ".join([seg.text for seg in segments]).strip()
        elapsed = time.time() - start
        
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
                    # Wake word detection mode
                    self.listen_wake_word()
                elif self.session_state == "active" and not self.robot_speaking:
                    # Transcription mode
                    self.listen_and_transcribe()
                else:
                    time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("\n[AudioInput] Stopping...")
            self.client.loop_stop()
            self.client.disconnect()

if __name__ == "__main__":
    audio = AudioInput()
    audio.start()
