#!/usr/bin/env python3
"""
STANDALONE WAKE WORD DETECTION SERVICE
Listens for "Hey Jarvis" and publishes to MQTT
100% decoupled from transcription
"""

import sounddevice as sd
import numpy as np
from openwakeword.model import Model
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
CHUNK_SAMPLES = 2000  # CRITICAL: Must be 2000 for proper wake word timing
WAKE_THRESHOLD = 0.1  # Original sensitivity
COOLDOWN_DURATION = 10.0  # Total cooldown: 10 seconds of complete silence
MIN_VOLUME_FOR_DETECTION = 350  # Minimum volume to consider as valid speech

# ============================================================================
# MQTT SETUP
# ============================================================================
with open('config/mqtt.yaml', 'r') as f:
    mqtt_config = yaml.safe_load(f)

broker = mqtt_config['mqtt']['broker']
port = mqtt_config['mqtt']['port']
topic_wake_detected = mqtt_config['topics']['session']['wake_detected']

mqtt_connected_once = False

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="wakeword_service")

def on_connect(client, userdata, flags, rc, properties=None):
    global mqtt_connected_once
    if not mqtt_connected_once:
        print(f"[{ts()}] [WAKEWORD] Connected to MQTT broker (rc={rc})")
        mqtt_connected_once = True

client.on_connect = on_connect
client.connect(broker, port, 60)
client.loop_start()

# ============================================================================
# WAKE WORD MODEL
# ============================================================================
print(f"[{ts()}] [WAKEWORD] Loading OpenWakeWord model...")
oww = Model()
print(f"[{ts()}] [WAKEWORD] ✓ Models available: {list(oww.models.keys())}")
print(f"[{ts()}] [WAKEWORD] ✓ Threshold: {WAKE_THRESHOLD}")
print(f"[{ts()}] [WAKEWORD] ✓ Cooldown: {COOLDOWN_DURATION}s")
print(f"[{ts()}] [WAKEWORD] ✓ Min volume: {MIN_VOLUME_FOR_DETECTION}")

# ============================================================================
# STATE TRACKING
# ============================================================================
last_detection_time = 0
in_cooldown = False  # Simple flag to track cooldown state

# ============================================================================
# AUDIO STREAM
# ============================================================================
print(f"[{ts()}] [WAKEWORD] Opening audio stream (device={MIC_DEVICE}, rate={MIC_RATE}, chunk={CHUNK_SAMPLES})...")
stream = sd.InputStream(
    device=MIC_DEVICE,
    samplerate=MIC_RATE,
    dtype='int16',
    channels=1,
    blocksize=CHUNK_SAMPLES  # CRITICAL: Must match CHUNK_SAMPLES
)
stream.start()
print(f"[{ts()}] [WAKEWORD] ✓ Listening for 'Hey Jarvis'...\n")

# ============================================================================
# MAIN LOOP
# ============================================================================
try:
    while True:
        # Read audio chunk
        indata, overflowed = stream.read(CHUNK_SAMPLES)
        audio_48k = np.frombuffer(indata, dtype=np.int16)
        
        # Check volume
        volume = int(np.abs(audio_48k).mean())
        
        # Skip if too quiet (noise floor)
        if volume < 300:
            continue
        
        # ====================================================================
        # COOLDOWN LOGIC - Absolute priority, blocks everything
        # ====================================================================
        if in_cooldown:
            time_since_detection = time.time() - last_detection_time
            remaining = COOLDOWN_DURATION - time_since_detection
            
            if remaining > 0:
                # Still in cooldown - show countdown and skip EVERYTHING
                if int(time_since_detection * 2) % 2 == 0:  # Every ~0.5s
                    print(f"\r[{ts()}] [WAKEWORD] 🔒 COOLDOWN: {remaining:.1f}s remaining...    ", end='', flush=True)
                continue  # Skip model processing entirely
            else:
                # Cooldown expired - reset everything and resume
                in_cooldown = False
                oww.reset()
                oww.reset()
                oww.reset()  # Triple reset to fully clear state
                print(f"\n[{ts()}] [WAKEWORD] ✅ Cooldown complete, resuming detection...\n")
        
        # ====================================================================
        # NORMAL DETECTION LOGIC (only runs when NOT in cooldown)
        # ====================================================================
        
        # CRITICAL: Decimate 48kHz -> 16kHz using EXACT working method
        trim_len = (len(audio_48k) // 3) * 3
        audio_16k = audio_48k[:trim_len].reshape(-1, 3).mean(axis=1).astype(np.int16)
        
        # Run wake word detection
        prediction = oww.predict(audio_16k)
        jarvis_score = prediction.get('hey_jarvis', 0.0)
        
        # Check for detection
        if jarvis_score > WAKE_THRESHOLD:
            # Additional volume check to filter false positives
            if volume < MIN_VOLUME_FOR_DETECTION:
                print(f"[{ts()}] [WAKEWORD] ⚠️  Ignored: score={jarvis_score:.3f} but volume too low ({volume} < {MIN_VOLUME_FOR_DETECTION})")
                oww.reset()  # Reset model after rejecting
                continue
            
            print(f"\n[{ts()}] [WAKEWORD] 🔊 DETECTED! score={jarvis_score:.3f} volume={volume}")
            
            # Publish to MQTT
            client.publish(topic_wake_detected, f"{jarvis_score}")
            print(f"[{ts()}] [WAKEWORD] ✓ Published to MQTT: {topic_wake_detected}")
            
            # Aggressively reset model multiple times
            oww.reset()
            oww.reset()
            oww.reset()
            print(f"[{ts()}] [WAKEWORD] ✓ Model buffer reset")
            
            # Enter cooldown mode
            last_detection_time = time.time()
            in_cooldown = True
            ignore_until = datetime.fromtimestamp(last_detection_time + COOLDOWN_DURATION).strftime("%H:%M:%S")
            print(f"[{ts()}] [WAKEWORD] 🔒 COOLDOWN MODE: No detections until {ignore_until}\n")

except KeyboardInterrupt:
    print(f"\n[{ts()}] [WAKEWORD] Stopping...")
    stream.stop()
    stream.close()
    client.loop_stop()
    client.disconnect()
    print(f"[{ts()}] [WAKEWORD] ✓ Stopped")
