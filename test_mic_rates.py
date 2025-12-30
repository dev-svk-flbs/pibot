#!/usr/bin/env python3
"""
Check supported sample rates for microphone
"""

import sounddevice as sd

MIC_INDEX = 1

print("="*80)
print("MICROPHONE CAPABILITIES")
print("="*80)

device_info = sd.query_devices(MIC_INDEX)
print(f"\nDevice: {device_info['name']}")
print(f"Max Input Channels: {device_info['max_input_channels']}")
print(f"Default Sample Rate: {device_info['default_samplerate']}")

print("\n" + "="*80)
print("Testing supported sample rates...")
print("="*80)

test_rates = [8000, 16000, 22050, 32000, 44100, 48000, 96000]

supported = []
for rate in test_rates:
    try:
        sd.check_input_settings(device=MIC_INDEX, samplerate=rate, channels=1)
        print(f"✓ {rate:6d} Hz - SUPPORTED")
        supported.append(rate)
    except Exception as e:
        print(f"✗ {rate:6d} Hz - NOT SUPPORTED")

print("\n" + "="*80)
print(f"Supported rates: {supported}")
print("="*80)
