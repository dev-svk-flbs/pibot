#!/usr/bin/env python3
"""
Test 1: MQTT Broker Connectivity
Verifies MQTT broker is running and can send/receive messages
"""

import paho.mqtt.client as mqtt
import time
import sys

print("=" * 60)
print("TEST 1: MQTT Broker Connectivity")
print("=" * 60)

test_passed = False
message_received = False

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"✓ Connected to broker (rc={rc})")
    client.subscribe("test/ping")

def on_message(client, userdata, msg):
    global message_received
    payload = msg.payload.decode('utf-8')
    print(f"✓ Received message: '{payload}' on topic: {msg.topic}")
    message_received = True

# Create client
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test_mqtt")
client.on_connect = on_connect
client.on_message = on_message

try:
    # Connect
    print("Connecting to localhost:1883...")
    client.connect("localhost", 1883, 60)
    client.loop_start()
    
    time.sleep(1)
    
    # Publish test message
    print("Publishing test message...")
    client.publish("test/ping", "Hello MQTT!")
    
    # Wait for message
    time.sleep(2)
    
    if message_received:
        print("\n✅ TEST PASSED - MQTT broker is working!")
        test_passed = True
    else:
        print("\n❌ TEST FAILED - No message received")
    
    client.loop_stop()
    client.disconnect()

except Exception as e:
    print(f"\n❌ TEST FAILED - Error: {e}")

print("=" * 60)
sys.exit(0 if test_passed else 1)
