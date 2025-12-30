#!/usr/bin/env python3
"""
Test 2: Session Manager State Transitions
Tests: IDLE → ACTIVE → SPEAKING → ACTIVE → IDLE
"""

import paho.mqtt.client as mqtt
import time
import sys

print("=" * 60)
print("TEST 2: Session Manager State Transitions")
print("=" * 60)

current_state = None
test_sequence = []
expected_sequence = ["active", "speaking", "active", "idle"]  # Don't expect initial idle

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"✓ Connected to broker")
    client.subscribe("session/state")
    client.subscribe("robot/emotion")

def on_message(client, userdata, msg):
    global current_state, test_sequence
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    
    if topic == "session/state":
        current_state = payload
        test_sequence.append(payload)
        print(f"  State changed: {payload}")
    elif topic == "robot/emotion":
        print(f"  Emotion: {payload}")

# Create client
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test_session")
client.on_connect = on_connect
client.on_message = on_message

try:
    print("\n⚠️  Make sure Session Manager is running in another terminal!")
    print("   Run: cd /home/saptapi/robot && source venv/bin/activate && python modules/session_manager.py\n")
    
    input("Press Enter when Session Manager is running...")
    
    # Connect
    client.connect("localhost", 1883, 60)
    client.loop_start()
    
    time.sleep(1)
    test_sequence = []  # Clear initial state
    
    print("\n--- Test Sequence ---")
    
    # Test 1: Wake word → ACTIVE
    print("\n1. Simulating wake word detection...")
    client.publish("session/wake_detected", "0.95")
    time.sleep(3)  # Wait longer for state to stabilize
    
    # Test 2: Robot starts speaking → SPEAKING
    print("\n2. Simulating robot speaking...")
    client.publish("robot/speaking", "true")
    time.sleep(3)  # Wait longer
    
    # Test 3: Robot stops speaking → ACTIVE
    print("\n3. Simulating robot finished speaking...")
    client.publish("robot/speaking", "false")
    time.sleep(3)  # Wait longer
    
    # Test 4: User says goodbye → IDLE
    print("\n4. Simulating goodbye phrase...")
    client.publish("audio/transcription", "Thank you, goodbye!")
    time.sleep(3)  # Wait longer
    
    client.loop_stop()
    client.disconnect()
    
    print("\n--- Results ---")
    print(f"Expected sequence: {expected_sequence}")
    print(f"Actual sequence:   {test_sequence}")
    
    if test_sequence == expected_sequence:
        print("\n✅ TEST PASSED - All state transitions work correctly!")
        sys.exit(0)
    else:
        print("\n❌ TEST FAILED - State sequence doesn't match")
        sys.exit(1)

except KeyboardInterrupt:
    print("\n\n❌ TEST INTERRUPTED")
    client.loop_stop()
    client.disconnect()
    sys.exit(1)
except Exception as e:
    print(f"\n❌ TEST FAILED - Error: {e}")
    sys.exit(1)
