#!/usr/bin/env python3
"""
Wake Word Test - Using OFFICIAL OpenWakeWord settings
16kHz native, 1280 chunk size (using sounddevice instead of pyaudio)
"""

import sounddevice as sd
import numpy as np
from openwakeword.model import Model
from datetime import datetime

def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

# OFFICIAL settings from OpenWakeWord repository
RATE = 16000  # Native 16kHz - NO decimation needed!
CHUNK = 1280  # Official chunk size
THRESHOLD = 0.6

print(f"[{ts()}] Loading OpenWakeWord model...")
oww = Model()
print(f"[{ts()}] ✓ Models loaded: {list(oww.models.keys())}")
print(f"[{ts()}] Detection threshold: {THRESHOLD}")
print(f"[{ts()}] Using official settings: 16kHz, {CHUNK} samples")
print()

# Open microphone at 16kHz (NO decimation!)
mic_stream = sd.InputStream(
    device=None,
    samplerate=RATE,
    dtype='int16',
    channels=1,
    blocksize=CHUNK
)

print(f"[{ts()}] ✓ Microphone opened. Listening for 'Hey Jarvis'...")
print(f"[{ts()}] Press Ctrl+C to stop\n")
print("=" * 80)

detection_count = 0
mic_stream.start()

try:
    while True:
        # Get audio - read exactly CHUNK samples
        audio_data, overflowed = mic_stream.read(CHUNK)
        audio_data = np.frombuffer(audio_data, dtype=np.int16)
        
        # Calculate volume
        volume = np.abs(audio_data).mean()
        
        # Feed to OpenWakeWord - NO decimation, already 16kHz!
        prediction = oww.predict(audio_data)
        
        # Show live volume
        if volume > 50:
            print(f"\r[Vol: {volume:6.0f}] ", end='', flush=True)
        
        # Check hey_jarvis
        if 'hey_jarvis' in prediction:
            score = prediction['hey_jarvis']
            
            # Show scores > 0.1
            if score > 0.1:
                print(f"\n[{ts()}] 🔍 hey_jarvis: {score:.3f} (vol: {volume:.0f})", end='')
                
                if score > THRESHOLD:
                    print(" ✓ DETECTED!")
                    detection_count += 1
                    print(f"[{ts()}] 🔊 WAKE WORD #{detection_count}")
                    print(f"[{ts()}]    Score: {score:.3f}")
                    print(f"[{ts()}]    Volume: {volume:.0f}")
                    print(f"[{ts()}]    Buffer: {list(oww.prediction_buffer['hey_jarvis'])[-5:]}")
                    print("-" * 80)
                else:
                    print(" (below threshold)")

except KeyboardInterrupt:
    print(f"\n\n[{ts()}] Stopping...")
    mic_stream.stop()
    mic_stream.close()
    print(f"[{ts()}] ✓ Total detections: {detection_count}")
