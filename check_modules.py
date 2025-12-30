#!/usr/bin/env python3
"""
Quick diagnostic to check all modules are running
"""

import paho.mqtt.client as mqtt
import yaml
import time

def check_modules():
    print("\n" + "="*60)
    print("MODULE STATUS CHECK")
    print("="*60)
    
    with open('config/mqtt.yaml', 'r') as f:
        mqtt_config = yaml.safe_load(f)
    
    broker = mqtt_config['mqtt']['broker']
    port = mqtt_config['mqtt']['port']
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="diagnostic")
    
    modules_seen = set()
    
    def on_message(client, userdata, msg):
        topic = msg.topic
        # Infer module from topic
        if topic.startswith("session/"):
            modules_seen.add("session_manager")
        elif topic.startswith("audio/"):
            modules_seen.add("audio_input")
        elif topic.startswith("llm/"):
            modules_seen.add("llm_client")
        elif topic.startswith("robot/speaking"):
            modules_seen.add("tts_output")
        
        print(f"  📨 {topic}: {msg.payload.decode()[:50]}")
    
    def on_connect(client, userdata, flags, rc, properties=None):
        print("\n✓ Connected to MQTT broker")
        print("\nListening for module activity (10 seconds)...\n")
        client.subscribe("#")  # Subscribe to all topics
    
    client.on_connect = on_connect
    client.on_message = on_message
    
    client.connect(broker, port, 60)
    client.loop_start()
    
    # Trigger a wake word detection
    time.sleep(2)
    print("\n🔔 Sending test wake word signal...")
    client.publish("session/wake_detected", "0.99")
    
    time.sleep(8)
    
    client.loop_stop()
    client.disconnect()
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print("\nModules detected:")
    if "session_manager" in modules_seen:
        print("  ✓ Session Manager")
    else:
        print("  ✗ Session Manager NOT RUNNING")
    
    if "audio_input" in modules_seen:
        print("  ✓ Audio Input")
    else:
        print("  ⚠ Audio Input (may not have published yet)")
    
    if "llm_client" in modules_seen:
        print("  ✓ LLM Client")
    else:
        print("  ✗ LLM Client NOT RUNNING")
    
    if "tts_output" in modules_seen:
        print("  ✓ TTS Output")
    else:
        print("  ✗ TTS Output NOT RUNNING")
    
    print("\n" + "="*60)
    
    if len(modules_seen) < 3:
        print("\n⚠ WARNING: Not all modules are running!")
        print("\nStart missing modules:")
        if "session_manager" not in modules_seen:
            print("  Terminal 1: python modules/session_manager.py")
        if "llm_client" not in modules_seen:
            print("  Terminal 2: python modules/llm_client.py")
        if "tts_output" not in modules_seen:
            print("  Terminal 3: python modules/tts_output.py")
        print("  Terminal 4: python modules/audio_input.py")

if __name__ == "__main__":
    check_modules()
