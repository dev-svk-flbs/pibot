#!/usr/bin/env python3
"""MINIMAL WAKE WORD DETECTION"""
import sounddevice as sd
import numpy as np
from openwakeword.model import Model
import paho.mqtt.client as mqtt
import yaml
import time
import sys
from datetime import datetime

# Logging
sys.stdout = open('logs/wakeword.log', 'a', buffering=1)
sys.stderr = sys.stdout

# Config - Find FIRST USB PnP mic (for wake word detection)
import sounddevice as sd
devices = sd.query_devices()
usb_mics = [(i, dev) for i, dev in enumerate(devices) if 'USB PnP Sound Device' in dev['name'] and dev['max_input_channels'] > 0]
if len(usb_mics) == 0:
    raise Exception("No USB PnP microphones found!")
MIC_DEVICE = usb_mics[0][0]  # First USB PnP mic
print(f"[WAKEWORD] Using device {MIC_DEVICE}: {usb_mics[0][1]['name']}")

MIC_RATE = 48000
CHUNK_SAMPLES = 2000
WAKE_THRESHOLD = 0.1
last_detect = 0

# MQTT
with open('config/mqtt.yaml', 'r') as f:
    mqtt_config = yaml.safe_load(f)
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(mqtt_config['mqtt']['broker'], mqtt_config['mqtt']['port'], 60)
client.loop_start()

# Model
oww = Model()
print(f"Listening for 'Hey Jarvis' (threshold={WAKE_THRESHOLD})...")

# Audio stream
stream = sd.InputStream(device=MIC_DEVICE, samplerate=MIC_RATE, dtype='int16', channels=1, blocksize=CHUNK_SAMPLES)
stream.start()

# Main loop
try:
    while True:
        # Read audio
        indata, _ = stream.read(CHUNK_SAMPLES)
        audio_48k = np.frombuffer(indata, dtype=np.int16)
        
        # Decimate to 16kHz
        trim_len = (len(audio_48k) // 3) * 3
        audio_16k = audio_48k[:trim_len].reshape(-1, 3).mean(axis=1).astype(np.int16)
        
        # Detect
        prediction = oww.predict(audio_16k)
        score = prediction.get('hey_jarvis', 0.0)
        
        if score > WAKE_THRESHOLD and time.time() - last_detect > 1:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] DETECTED! score={score:.3f}")
            client.publish(mqtt_config['topics']['session']['wake_detected'], f"{score}")
            oww.reset()
            last_detect = time.time()

except KeyboardInterrupt:
    stream.stop()
    stream.close()
    client.disconnect()
    print("Stopped")
