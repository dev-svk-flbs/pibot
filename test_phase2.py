#!/usr/bin/env python3
"""
Test Phase 2: End-to-end LLM + TTS integration
Simulates: wake word → user question → LLM response → TTS playback
"""

import paho.mqtt.client as mqtt
import yaml
import time
import sys

class Phase2Tester:
    def __init__(self):
        with open('config/mqtt.yaml', 'r') as f:
            mqtt_config = yaml.safe_load(f)
        self.topics = mqtt_config['topics']
        
        self.messages_received = []
        
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="phase2_tester")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"✓ Connected to MQTT broker")
        # Subscribe to all relevant topics
        client.subscribe(self.topics['session']['state'])
        client.subscribe(self.topics['llm']['response'])
        client.subscribe(self.topics['robot']['speaking'])
        client.subscribe(self.topics['robot']['emotion'])
        
    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        timestamp = time.time()
        
        self.messages_received.append({
            'topic': topic,
            'payload': payload,
            'time': timestamp
        })
        
        print(f"  [{topic}] = {payload}")
    
    def run_test(self):
        """Run end-to-end Phase 2 test"""
        print("\n" + "="*60)
        print("PHASE 2 TEST: LLM + TTS Integration")
        print("="*60)
        
        # Connect
        with open('config/mqtt.yaml', 'r') as f:
            mqtt_config = yaml.safe_load(f)
        broker = mqtt_config['mqtt']['broker']
        port = mqtt_config['mqtt']['port']
        
        self.client.connect(broker, port, 60)
        self.client.loop_start()
        
        time.sleep(1)
        
        print("\n--- Test 1: Wake Word Detection ---")
        print("Sending wake word signal...")
        self.client.publish(self.topics['session']['wake_detected'], "wake_word_detected")
        time.sleep(2)
        
        # Check if session went to ACTIVE
        session_states = [m for m in self.messages_received if m['topic'] == self.topics['session']['state']]
        if session_states and session_states[-1]['payload'] == 'active':
            print("✓ Session transitioned to ACTIVE")
        else:
            print("✗ Session did not activate")
            return False
        
        print("\n--- Test 2: User Question → LLM Response ---")
        print("Sending user question: 'What is the capital of France?'")
        self.client.publish(self.topics['audio']['transcription'], "What is the capital of France?")
        
        # Wait for LLM response
        print("Waiting for LLM response (max 10 seconds)...")
        start_time = time.time()
        llm_responded = False
        
        while time.time() - start_time < 10:
            llm_responses = [m for m in self.messages_received if m['topic'] == self.topics['llm']['response']]
            if llm_responses:
                response_text = llm_responses[-1]['payload']
                print(f"✓ LLM Response: {response_text[:100]}...")
                llm_responded = True
                break
            time.sleep(0.5)
        
        if not llm_responded:
            print("✗ No LLM response received")
            return False
        
        print("\n--- Test 3: TTS Speaking Flag ---")
        print("Checking robot/speaking flag...")
        time.sleep(1)
        
        speaking_msgs = [m for m in self.messages_received if m['topic'] == self.topics['robot']['speaking']]
        if speaking_msgs:
            # Should have seen "true" and "false"
            speaking_values = [m['payload'] for m in speaking_msgs]
            if 'true' in speaking_values:
                print(f"✓ TTS speaking flag set: {speaking_values}")
            else:
                print("✗ TTS speaking flag not set correctly")
                return False
        else:
            print("✗ No speaking flag messages")
            return False
        
        print("\n--- Test 4: Follow-up Question ---")
        print("Sending follow-up: 'Tell me more about Paris'")
        time.sleep(2)  # Wait for TTS to finish
        self.client.publish(self.topics['audio']['transcription'], "Tell me more about Paris")
        
        time.sleep(5)
        
        # Check for second response
        llm_responses = [m for m in self.messages_received if m['topic'] == self.topics['llm']['response']]
        if len(llm_responses) >= 2:
            print(f"✓ Follow-up response: {llm_responses[-1]['payload'][:100]}...")
        else:
            print("⚠ No follow-up response (may still be processing)")
        
        print("\n--- Test 5: Goodbye (Session End) ---")
        print("Sending goodbye phrase...")
        self.client.publish(self.topics['audio']['transcription'], "goodbye")
        time.sleep(2)
        
        session_states = [m for m in self.messages_received if m['topic'] == self.topics['session']['state']]
        if session_states and session_states[-1]['payload'] == 'idle':
            print("✓ Session returned to IDLE after goodbye")
        else:
            print("⚠ Session state: " + (session_states[-1]['payload'] if session_states else "unknown"))
        
        print("\n" + "="*60)
        print("PHASE 2 TEST COMPLETE")
        print("="*60)
        print(f"\nTotal messages received: {len(self.messages_received)}")
        
        self.client.loop_stop()
        self.client.disconnect()
        
        return True

if __name__ == "__main__":
    print("\n⚠ PREREQUISITES:")
    print("  1. Session Manager running (terminal 1)")
    print("  2. LLM Client running (terminal 2)")
    print("  3. TTS Output running (terminal 3)")
    print("\nPress Enter when ready, or Ctrl+C to cancel...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nTest cancelled")
        sys.exit(0)
    
    tester = Phase2Tester()
    tester.run_test()
