#!/usr/bin/env python3
"""
STANDALONE TRANSCRIPTION SERVICE - SIMPLIFIED (ARECORD VERSION)
Listens for wake word MQTT trigger, then records using ALSA (arecord) and transcribes.
100% decoupled from wake word detection.
"""

import subprocess
import os
import time
import threading
import yaml
import paho.mqtt.client as mqtt
from datetime import datetime
from faster_whisper import WhisperModel

# ============================================================================
# CONFIGURATION
# ============================================================================
# Hardcoded for simplicity/reliability on this specific Pi setup
# Based on 'arecord -l', we have card 0 and card 3. Previous logic used the second one.
MIC_DEVICE = "plughw:3,0" 
RECORDING_DURATION = 10  # Seconds
TEMP_FILENAME = "/tmp/recording.wav"
ARCHIVE_DIR = "recordings"

# Ensure recordings directory exists
os.makedirs(ARCHIVE_DIR, exist_ok=True)

def ts():
    """Timestamp for logs"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

# ============================================================================
# MQTT SETUP
# ============================================================================
with open('config/mqtt.yaml', 'r') as f:
    mqtt_config = yaml.safe_load(f)

broker = mqtt_config['mqtt']['broker']
port = mqtt_config['mqtt']['port']
topic_wake_detected = mqtt_config['topics']['session']['wake_detected']
topic_transcription = mqtt_config['topics']['audio']['transcription']

wake_word_detected = False
wake_word_lock = threading.Lock()
is_processing = False
last_wake_time = 0

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[{ts()}] [TRANSCRIBE] Connected to MQTT broker (rc={rc})")
    client.subscribe(topic_wake_detected)
    print(f"[{ts()}] [TRANSCRIBE] ✓ Subscribed to: {topic_wake_detected}")

def on_message(client, userdata, msg):
    global wake_word_detected, is_processing, last_wake_time
    
    if msg.topic == topic_wake_detected:
        current_time = time.time()
        if current_time - last_wake_time < 1.0: return # Debounce
        if is_processing: return # Ignore while busy
        
        score = msg.payload.decode('utf-8')
        print(f"\n[{ts()}] [TRANSCRIBE] 🔔 Wake word trigger received! (score={score})")
        
        with wake_word_lock:
            wake_word_detected = True
            last_wake_time = current_time

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="transcription_service")
client.on_connect = on_connect
client.on_message = on_message
client.connect(broker, port, 60)
client.loop_start()

# ============================================================================
# WHISPER MODEL
# ============================================================================
print(f"[{ts()}] [TRANSCRIBE] Loading Whisper model...")
whisper = WhisperModel("tiny", device="cpu", compute_type="int8", num_workers=1)
print(f"[{ts()}] [TRANSCRIBE] ✓ Whisper ready")

# ============================================================================
# CORE FUNCTIONS
# ============================================================================
def record_audio_alsa(filename, duration):
    """Record using native ALSA 'arecord' command - Most robust method"""
    print(f"[{ts()}] [TRANSCRIBE] 🎙️  Recording {duration}s via ALSA ({MIC_DEVICE})...")
    
    # Give wake word service a split second to release mic if needed
    time.sleep(0.2)
    
    cmd = [
        "arecord",
        "-D", MIC_DEVICE,
        "-f", "S16_LE",     # 16-bit Little Endian
        "-r", "16000",      # 16kHz (Whisper native)
        "-c", "1",          # Mono
        "-d", str(duration),# Duration
        "-t", "wav",        # WAV format
        "-q",               # Quiet mode
        filename
    ]
    
    try:
        # Run blocking call - this is what we want
        subprocess.run(cmd, check=True)
        
        # Verify file exists and has size
        if os.path.exists(filename) and os.path.getsize(filename) > 44:
            print(f"[{ts()}] [TRANSCRIBE] ✓ Recording complete")
            return True
        else:
            print(f"[{ts()}] [TRANSCRIBE] ❌ Recording failed: File empty or missing")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"[{ts()}] [TRANSCRIBE] ❌ arecord failed: {e}")
        return False
    except Exception as e:
        print(f"[{ts()}] [TRANSCRIBE] ❌ Unexpected error: {e}")
        return False

def transcribe_file(filename):
    """Transcribe the WAV file directly"""
    print(f"[{ts()}] [TRANSCRIBE] ⚡ Transcribing...")
    start = time.time()
    
    try:
        segments, info = whisper.transcribe(
            filename,
            language="en",
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200),
            beam_size=5
        )
        
        text = " ".join([seg.text.strip() for seg in segments]).strip()
        elapsed = time.time() - start
        
        if text:
            print(f"[{ts()}] [TRANSCRIBE] ✅ '{text}' ({elapsed:.2f}s)")
            return text
        else:
            print(f"[{ts()}] [TRANSCRIBE] ❌ No speech detected ({elapsed:.2f}s)")
            return None
            
    except Exception as e:
        print(f"[{ts()}] [TRANSCRIBE] ❌ Transcription error: {e}")
        return None

# ============================================================================
# MAIN LOOP
# ============================================================================
print(f"[{ts()}] [TRANSCRIBE] Ready and waiting...\n")

try:
    while True:
        should_process = False
        with wake_word_lock:
            if wake_word_detected:
                wake_word_detected = False
                should_process = True
                is_processing = True
        
        if should_process:
            try:
                # 1. Record
                if record_audio_alsa(TEMP_FILENAME, RECORDING_DURATION):
                    
                    # 2. Archive (copy for debugging) - DISABLED FOR PERFORMANCE
                    # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    # archive_path = os.path.join(ARCHIVE_DIR, f"question_{timestamp}.wav")
                    # subprocess.run(["cp", TEMP_FILENAME, archive_path])
                    # print(f"[{ts()}] [TRANSCRIBE] 💾 Archived: {archive_path}")
                    
                    # 3. Transcribe
                    text = transcribe_file(TEMP_FILENAME)
                    
                    # 4. Publish
                    if text:
                        client.publish(topic_transcription, text)
                        print(f"[{ts()}] [TRANSCRIBE] ✓ Published to MQTT")
                
                print(f"\n[{ts()}] [TRANSCRIBE] Ready for next wake word...\n")
                
            finally:
                is_processing = False
        
        time.sleep(0.1)

except KeyboardInterrupt:
    print(f"\n[{ts()}] [TRANSCRIBE] Stopping...")
    client.loop_stop()
    client.disconnect()
