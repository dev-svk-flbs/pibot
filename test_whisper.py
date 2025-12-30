#!/usr/bin/env python3
"""
Standalone Whisper transcription test - find optimal audio settings
"""

import numpy as np
from faster_whisper import WhisperModel
import sounddevice as sd
import time

print("="*80)
print("WHISPER TRANSCRIPTION TEST")
print("="*80)

# Load Whisper
print("\nLoading Whisper tiny model...")
whisper = WhisperModel("tiny", device="cpu", compute_type="int8")
print("✓ Whisper loaded")

MIC_INDEX = 1
DURATION = 5  # seconds

# Test different configurations
configs = [
    {"name": "16kHz direct", "rate": 16000, "dtype": "float32"},
    {"name": "48kHz decimated", "rate": 48000, "dtype": "int16"},
    {"name": "44.1kHz float", "rate": 44100, "dtype": "float32"},
]

print("\n" + "="*80)
print("Testing different audio configurations...")
print("="*80)

for config in configs:
    print(f"\n{'='*80}")
    print(f"CONFIG: {config['name']}")
    print(f"Rate: {config['rate']} Hz, Dtype: {config['dtype']}")
    print(f"{'='*80}")
    
    input(f"\nPress ENTER, then say something for {DURATION} seconds...")
    
    # Record audio
    print(f"🎧 Recording for {DURATION}s...")
    start = time.time()
    
    audio_data = sd.rec(
        int(DURATION * config['rate']),
        samplerate=config['rate'],
        channels=1,
        dtype=config['dtype'],
        device=MIC_INDEX
    )
    sd.wait()
    
    record_time = time.time() - start
    print(f"✓ Recorded in {record_time:.2f}s")
    
    audio_data = audio_data.flatten()
    
    # Prepare for Whisper (needs 16kHz float32)
    if config['rate'] == 48000 and config['dtype'] == 'int16':
        # Decimate by 3
        trim_len = (len(audio_data) // 3) * 3
        audio_16k = audio_data[:trim_len].reshape(-1, 3).mean(axis=1).astype(np.float32)
        # Normalize int16 to float32
        audio_16k = audio_16k / 32768.0
    elif config['rate'] == 16000:
        audio_16k = audio_data
    elif config['rate'] == 44100:
        # Resample 44.1 -> 16kHz
        from scipy import signal
        num_samples = int(len(audio_data) * 16000 / config['rate'])
        audio_16k = signal.resample(audio_data, num_samples)
    
    # Check audio level
    volume = np.abs(audio_16k).mean()
    print(f"Audio volume: {volume:.6f}")
    
    if volume < 0.001:
        print("⚠ WARNING: Very low volume detected!")
    
    # Transcribe
    print("🔄 Transcribing...")
    start = time.time()
    
    segments, info = whisper.transcribe(
        audio_16k,
        beam_size=1,
        language="en",
        condition_on_previous_text=False
    )
    
    transcribe_time = time.time() - start
    
    # Get text
    text = " ".join([seg.text for seg in segments]).strip()
    
    print(f"✓ Transcribed in {transcribe_time:.2f}s")
    print(f"\n📝 RESULT: '{text}'")
    
    if not text:
        print("❌ No transcription (silence or failed)")
    
    print(f"\nTotal time: {record_time + transcribe_time:.2f}s")

print("\n" + "="*80)
print("TESTING COMPLETE")
print("="*80)
print("\nReview results above to choose best config for your use case.")
