#!/usr/bin/env python3
"""
STANDALONE TRANSCRIPTION SERVICE
Listens for wake word MQTT trigger, then records and transcribes
100% decoupled from wake word detection
"""

import sounddevice as sd
import numpy as np
from scipy import signal as scipy_signal
from faster_whisper import WhisperModel
import paho.mqtt.client as mqtt
import yaml
import time
from datetime import datetime

def ts():
    """Timestamp for logs"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

# ============================================================================
# CONFIGURATION
# ============================================================================
MIC_DEVICE = None  # Auto-select (or set to 0 or 2 for specific USB mic)
MIC_RATE = 48000  # USB mic native rate
WHISPER_RATE = 16000  # Whisper needs 16kHz

# VAD settings for recording
CHUNK_DURATION = 0.5  # 500ms chunks
SILENCE_THRESHOLD = 300  # Volume threshold
SILENCE_DURATION = 2.5  # Stop after 2.5s silence
MAX_RECORDING = 30  # Max 30s recording

# ============================================================================
# MQTT SETUP
# ============================================================================
with open('config/mqtt.yaml', 'r') as f:
    mqtt_config = yaml.safe_load(f)

broker = mqtt_config['mqtt']['broker']
port = mqtt_config['mqtt']['port']
topic_wake_detected = mqtt_config['topics']['session']['wake_detected']
topic_transcription = mqtt_config['topics']['audio']['transcription']

wake_word_detected = False  # Flag set by MQTT
mqtt_connected_once = False

def on_connect(client, userdata, flags, rc, properties=None):
    global mqtt_connected_once
    if not mqtt_connected_once:
        print(f"[{ts()}] [TRANSCRIBE] Connected to MQTT broker (rc={rc})")
        mqtt_connected_once = True
    client.subscribe(topic_wake_detected)
    if not mqtt_connected_once:
        print(f"[{ts()}] [TRANSCRIBE] ✓ Subscribed to: {topic_wake_detected}")

def on_message(client, userdata, msg):
    global wake_word_detected
    if msg.topic == topic_wake_detected:
        score = msg.payload.decode('utf-8')
        print(f"\n[{ts()}] [TRANSCRIBE] 🔔 Wake word trigger received! (score={score})")
        wake_word_detected = True

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="transcription_service")
client.on_connect = on_connect
client.on_message = on_message
client.connect(broker, port, 60)
client.loop_start()

# ============================================================================
# WHISPER MODEL - Optimized for speed
# ============================================================================
print(f"[{ts()}] [TRANSCRIBE] Loading Whisper model (optimized for speed)...")
whisper = WhisperModel(
    "tiny",  # Fastest model
    device="cpu",
    compute_type="int8",  # Fastest compute type
    num_workers=1  # Single worker for Pi
)
print(f"[{ts()}] [TRANSCRIBE] ✓ Whisper ready")
print(f"[{ts()}] [TRANSCRIBE] ✓ Waiting for wake word triggers...\n")

# ============================================================================
# RECORDING FUNCTION
# ============================================================================
def record_with_vad():
    """Record audio using Voice Activity Detection"""
    chunk_samples = int(CHUNK_DURATION * MIC_RATE)
    silence_chunks_needed = int(SILENCE_DURATION / CHUNK_DURATION)
    max_chunks = int(MAX_RECORDING / CHUNK_DURATION)
    
    print(f"[{ts()}] [TRANSCRIBE] 🎙️  Recording (VAD-based)...")
    
    # Open stream
    stream = sd.InputStream(
        device=MIC_DEVICE,
        samplerate=MIC_RATE,
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
            chunk, _ = stream.read(chunk_samples)
            audio_chunk = np.frombuffer(chunk, dtype=np.int16)
            
            volume = np.abs(audio_chunk).mean()
            
            if volume > SILENCE_THRESHOLD:
                silence_count = 0
                speech_detected = True
                print("🗣️", end='', flush=True)
            else:
                if speech_detected:
                    silence_count += 1
                    print(".", end='', flush=True)
            
            recorded_chunks.append(audio_chunk)
            total_chunks += 1
            
            # Stop on silence after speech
            if speech_detected and silence_count >= silence_chunks_needed:
                print()
                duration = total_chunks * CHUNK_DURATION
                print(f"[{ts()}] [TRANSCRIBE] ✓ Recording stopped on silence ({duration:.1f}s)")
                break
    
    finally:
        stream.stop()
        stream.close()
    
    if not speech_detected:
        print(f"\n[{ts()}] [TRANSCRIBE] ❌ No speech detected")
        return None
    
    # Combine chunks
    audio_48k = np.concatenate(recorded_chunks)
    return audio_48k

# ============================================================================
# TRANSCRIPTION FUNCTION - Optimized for speed
# ============================================================================
def transcribe_audio(audio_48k):
    """Transcribe audio with speed optimizations"""
    # Resample 48kHz -> 16kHz
    audio_16k = scipy_signal.resample_poly(audio_48k, WHISPER_RATE, MIC_RATE)
    audio_16k = audio_16k.astype(np.float32) / 32768.0  # Normalize
    
    print(f"[{ts()}] [TRANSCRIBE] ⚡ Transcribing (fast mode)...")
    start = time.time()
    
    # Speed optimizations:
    # - beam_size=1: Fastest (vs 5 default)
    # - vad_filter=True: Skip silence
    # - language="en": Skip detection
    # - condition_on_previous_text=False: Faster, less context dependency
    segments, _ = whisper.transcribe(
        audio_16k,
        beam_size=1,
        language="en",
        vad_filter=True,
        condition_on_previous_text=False
    )
    
    text = " ".join([seg.text.strip() for seg in segments]).strip()
    elapsed = time.time() - start
    
    if text:
        print(f"[{ts()}] [TRANSCRIBE] ✅ '{text}' ({elapsed:.2f}s)")
        return text
    else:
        print(f"[{ts()}] [TRANSCRIBE] ❌ No text detected ({elapsed:.2f}s)")
        return None

# ============================================================================
# MAIN LOOP
# ============================================================================
print(f"[{ts()}] [TRANSCRIBE] Ready and waiting...\n")

try:
    while True:
        if wake_word_detected:
            wake_word_detected = False  # Reset flag
            
            # Record audio
            audio = record_with_vad()
            
            if audio is not None:
                # Transcribe
                text = transcribe_audio(audio)
                
                if text:
                    # Publish to MQTT
                    client.publish(topic_transcription, text)
                    print(f"[{ts()}] [TRANSCRIBE] ✓ Published to MQTT: {topic_transcription}")
            
            print(f"\n[{ts()}] [TRANSCRIBE] Ready for next wake word...\n")
        
        time.sleep(0.1)  # Small sleep to prevent CPU spin

except KeyboardInterrupt:
    print(f"\n[{ts()}] [TRANSCRIBE] Stopping...")
    client.loop_stop()
    client.disconnect()
    print(f"[{ts()}] [TRANSCRIBE] ✓ Stopped")
