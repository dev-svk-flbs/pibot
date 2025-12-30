#!/usr/bin/env python3
"""
Test 3: Session Timeout
Tests that session returns to IDLE after 30s of inactivity
"""

import paho.mqtt.client as mqtt
import time
import sys

print("=" * 60)
print("TEST 3: Session Timeout (30 seconds)")
print("=" * 60)

current_state = None
state_changes = []

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"✓ Connected to broker")
    client.subscribe("session/state")

def on_message(client, userdata, msg):
    global current_state, state_changes
    if msg.topic == "session/state":
        payload = msg.payload.decode('utf-8')
        current_state = payload
        state_changes.append((time.time(), payload))
        print(f"  [{time.strftime('%H:%M:%S')}] State: {payload}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test_timeout")
client.on_connect = on_connect
client.on_message = on_message

try:
    print("\n⚠️  Make sure Session Manager is running!")
    print("   Run: cd /home/saptapi/robot && source venv/bin/activate && python modules/session_manager.py\n")
    
    input("Press Enter to start timeout test...")
    
    client.connect("localhost", 1883, 60)
    client.loop_start()
    
    time.sleep(2)  # Wait for initial state
    state_changes = []  # Clear initial states
    
    print("\n1. Triggering wake word (IDLE → ACTIVE)...")
    client.publish("session/wake_detected", "0.95")
    time.sleep(3)  # Wait for state change
    
    if current_state != "active":
        print("❌ Failed to enter ACTIVE state")
        sys.exit(1)
    
    print("\n2. Waiting 30 seconds for timeout...")
    print("   (Session should return to IDLE after 30s of inactivity)")
    
    start_time = time.time()
    timeout_occurred = False
    
    for i in range(35):
        time.sleep(1)
        elapsed = int(time.time() - start_time)
        
        if current_state == "idle" and not timeout_occurred:
            timeout_occurred = True
            timeout_time = elapsed
            print(f"\n✓ Timeout occurred after {timeout_time} seconds")
        
        if i % 5 == 0:
            print(f"   ... {elapsed}s elapsed (state: {current_state})")
    
    client.loop_stop()
    client.disconnect()
    
    print("\n--- Results ---")
    if timeout_occurred and 28 <= timeout_time <= 32:
        print(f"✅ TEST PASSED - Timeout occurred at {timeout_time}s (expected ~30s)")
        sys.exit(0)
    else:
        print(f"❌ TEST FAILED - Timeout didn't occur properly")
        sys.exit(1)

except KeyboardInterrupt:
    print("\n\n❌ TEST INTERRUPTED")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ TEST FAILED - Error: {e}")
    sys.exit(1)
