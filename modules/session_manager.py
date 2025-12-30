#!/usr/bin/env python3
"""
Session Manager - State machine for conversation flow
Manages: IDLE → ACTIVE → SPEAKING states
"""

import paho.mqtt.client as mqtt
import yaml
import time
import threading
from enum import Enum

class SessionState(Enum):
    IDLE = "idle"
    ACTIVE = "active"
    SPEAKING = "speaking"

class SessionManager:
    def __init__(self):
        # Load config
        with open('config/mqtt.yaml', 'r') as f:
            mqtt_config = yaml.safe_load(f)
        with open('config/session.yaml', 'r') as f:
            session_config = yaml.safe_load(f)
        
        self.mqtt_config = mqtt_config
        self.session_config = session_config
        self.topics = mqtt_config['topics']
        
        # State
        self.state = SessionState.IDLE
        self.last_activity = time.time()
        self.timeout = session_config['session']['idle_timeout']
        self.goodbye_phrases = session_config['session']['goodbye_phrases']
        
        # MQTT client
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="session_manager")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        # Timeout checker
        self.timeout_thread = None
        self.running = False
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"[SessionManager] Connected to MQTT broker (rc={rc})")
        
        # Subscribe to relevant topics
        client.subscribe(self.topics['session']['wake_detected'])
        client.subscribe(self.topics['session']['command'])
        client.subscribe(self.topics['audio']['transcription'])
        client.subscribe(self.topics['robot']['speaking'])
        client.subscribe(self.topics['llm']['response'])
        
        # Publish initial state
        self.publish_state()
    
    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        # Session command (cancel/reset)
        if topic == self.topics['session']['command']:
            if payload == "cancel" or payload == "reset":
                print(f"[SessionManager] ⚠️  CANCEL command received! {self.state.value.upper()} → IDLE")
                self.set_state(SessionState.IDLE)
        
        # Wake word detected
        elif topic == self.topics['session']['wake_detected']:
            if self.state == SessionState.IDLE:
                print(f"[SessionManager] Wake word detected! IDLE → ACTIVE")
                self.last_activity = time.time()
                self.set_state(SessionState.ACTIVE)
        
        # User spoke (transcription received)
        elif topic == self.topics['audio']['transcription']:
            if self.state == SessionState.ACTIVE:
                print(f"[SessionManager] User said: {payload}")
                self.last_activity = time.time()
                
                # Check for goodbye phrases
                if any(phrase in payload.lower() for phrase in self.goodbye_phrases):
                    print(f"[SessionManager] Goodbye detected! ACTIVE → IDLE")
                    self.set_state(SessionState.IDLE)
                else:
                    # Publish command to LLM
                    self.client.publish(self.topics['llm']['request'], payload)
        
        # Robot started speaking
        elif topic == self.topics['robot']['speaking']:
            if payload == "true" and self.state == SessionState.ACTIVE:
                print(f"[SessionManager] Robot speaking. ACTIVE → SPEAKING")
                self.set_state(SessionState.SPEAKING)
            elif payload == "false" and self.state == SessionState.SPEAKING:
                print(f"[SessionManager] Robot finished. SPEAKING → ACTIVE")
                self.set_state(SessionState.ACTIVE)
                self.last_activity = time.time()
    
    def set_state(self, new_state):
        """Change state and publish"""
        self.state = new_state
        self.publish_state()
    
    def publish_state(self):
        """Publish current state to MQTT"""
        self.client.publish(self.topics['session']['state'], self.state.value, retain=True)
        self.client.publish(self.topics['robot']['emotion'], self.get_emotion(), retain=True)
    
    def get_emotion(self):
        """Map state to display emotion"""
        if self.state == SessionState.IDLE:
            return "sleeping"
        elif self.state == SessionState.ACTIVE:
            return "listening"
        elif self.state == SessionState.SPEAKING:
            return "talking"
    
    def check_timeout(self):
        """Background thread to check for idle timeout"""
        while self.running:
            time.sleep(1)
            if self.state == SessionState.ACTIVE:
                idle_time = time.time() - self.last_activity
                if idle_time > self.timeout:
                    print(f"[SessionManager] Timeout ({self.timeout}s). ACTIVE → IDLE")
                    self.set_state(SessionState.IDLE)
    
    def start(self):
        """Start the session manager"""
        print("[SessionManager] Starting...")
        
        # Connect to MQTT
        broker = self.mqtt_config['mqtt']['broker']
        port = self.mqtt_config['mqtt']['port']
        self.client.connect(broker, port, 60)
        
        # Start timeout checker
        self.running = True
        self.timeout_thread = threading.Thread(target=self.check_timeout, daemon=True)
        self.timeout_thread.start()
        
        # Start MQTT loop
        print(f"[SessionManager] Ready. State: {self.state.value}")
        self.client.loop_forever()
    
    def stop(self):
        """Stop the session manager"""
        print("[SessionManager] Stopping...")
        self.running = False
        self.client.disconnect()

if __name__ == "__main__":
    manager = SessionManager()
    try:
        manager.start()
    except KeyboardInterrupt:
        manager.stop()
