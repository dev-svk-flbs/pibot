#!/usr/bin/env python3
"""
Standalone wake word test - using EXACT pipeline from working code
"""

import numpy as np
from openwakeword.model import Model
import sounddevice as sd
import time

# Audio settings - EXACTLY like working code
CHANNELS = 1
RATE2 = 48000  # Record at 48kHz
CHUNK = 2000   # 2000 samples per chunk (same as old code)
MIC_INDEX = 1  # USB mic

print("="*80)
print("WAKE WORD DETECTION TEST")
print("="*80)
print(f"Microphone: Device {MIC_INDEX}")
print(f"Sample Rate: {RATE2} Hz")
print(f"Chunk Size: {CHUNK} samples")
print(f"Target: 16000 Hz (decimated by 3)")
print("="*80)

# Initialize OpenWakeWord with hey_jarvis
print("\nLoading OpenWakeWord models...")
owwModel = Model()

available = list(owwModel.models.keys())
print(f"Available models: {available}")

if 'hey_jarvis' not in available:
    print("\n❌ ERROR: hey_jarvis not found!")
    print("Download with: openwakeword-cli --download_model hey_jarvis")
    exit(1)
else:
    print("✓ hey_jarvis model loaded")

# Setup audio stream - EXACTLY like old code
print(f"\nOpening audio stream...")
stream = sd.InputStream(
    device=MIC_INDEX,
    samplerate=RATE2,
    dtype='int16',
    channels=CHANNELS,
    blocksize=CHUNK
)
stream.start()
print("✓ Stream started\n")

print("="*80)
print("LISTENING FOR 'HEY JARVIS'")
print("Say 'Hey Jarvis' to test detection")
print("Press Ctrl+C to exit")
print("="*80)
print()

# Detection settings
THRESHOLD = 0.3
last_detection = 0
detection_cooldown = 1.0  # 1 second between detections

try:
    while True:
        # Read audio chunk
        indata, overflowed = stream.read(CHUNK)
        
        if overflowed:
            print("⚠ Audio buffer overflow!")
        
        # Convert to numpy array
        audio_48k = np.frombuffer(indata, dtype=np.int16)
        
        # Decimate by 3: 48kHz -> 16kHz (EXACT method from old code)
        # Trim to multiple of 3
        trim_len = (len(audio_48k) // 3) * 3
        audio_16k = audio_48k[:trim_len].reshape(-1, 3).mean(axis=1).astype(np.int16)
        
        # Feed to OpenWakeWord
        prediction = owwModel.predict(audio_16k)
        
        # Check volume level
        volume = np.abs(audio_48k).mean()
        
        # Get hey_jarvis score
        jarvis_score = prediction.get('hey_jarvis', 0.0)
        
        # Show live scores when there's audio
        if volume > 100:  # Some audio activity
            # Show all scores in one line
            scores_str = " | ".join([f"{k}: {v:.3f}" for k, v in prediction.items()])
            print(f"[vol: {volume:6.0f}] {scores_str}", end='\r')
            
            # Highlight hey_jarvis if score is significant
            if jarvis_score > 0.1:
                print(f"\n>>> hey_jarvis: {jarvis_score:.3f} (threshold: {THRESHOLD})")
        
        # Wake word detected!
        if jarvis_score > THRESHOLD:
            current_time = time.time()
            
            # Cooldown to prevent multiple triggers
            if current_time - last_detection > detection_cooldown:
                print(f"\n{'='*80}")
                print(f"🔊 WAKE WORD DETECTED! Score: {jarvis_score:.3f}")
                print(f"{'='*80}\n")
                last_detection = current_time

except KeyboardInterrupt:
    print("\n\nStopping...")
    stream.stop()
    stream.close()
    print("Stream closed. Goodbye!")
