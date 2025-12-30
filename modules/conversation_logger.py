#!/usr/bin/env python3
"""
Conversation Logger - Records all interactions with timestamps
Subscribes to all MQTT topics and logs conversations to file
"""

import paho.mqtt.client as mqtt
import yaml
import json
from datetime import datetime
import os

class ConversationLogger:
    def __init__(self):
        # Load MQTT config
        with open('config/mqtt.yaml', 'r') as f:
            mqtt_config = yaml.safe_load(f)
        self.topics = mqtt_config['topics']
        
        # Log file setup
        self.log_dir = "logs"
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Create daily log file
        today = datetime.now().strftime("%Y-%m-%d")
        self.log_file = f"{self.log_dir}/conversations_{today}.log"
        self.json_file = f"{self.log_dir}/conversations_{today}.json"
        
        # In-memory conversation tracking
        self.current_session = {
            "session_id": None,
            "start_time": None,
            "wake_word_time": None,
            "user_question": None,
            "question_time": None,
            "llm_response": None,
            "response_time": None,
            "tts_start": None,
            "tts_end": None,
            "duration": None
        }
        
        self.all_sessions = []
        
        # MQTT
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="conversation_logger")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        print("[ConvLogger] Conversation Logger initialized")
        print(f"[ConvLogger] Logging to: {self.log_file}")
        
        # Write header to log file
        self.log("=" * 80)
        self.log(f"CONVERSATION LOG - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("=" * 80)
    
    def log(self, message):
        """Write to log file with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] {message}\n"
        
        with open(self.log_file, 'a') as f:
            f.write(log_line)
        
        print(f"[ConvLogger] {message}")
    
    def save_session_json(self):
        """Save all sessions to JSON file"""
        with open(self.json_file, 'w') as f:
            json.dump(self.all_sessions, f, indent=2)
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"[ConvLogger] Connected to MQTT broker (rc={rc})")
        
        # Subscribe to ALL relevant topics
        client.subscribe(self.topics['session']['wake_detected'])
        client.subscribe(self.topics['session']['state'])
        client.subscribe(self.topics['audio']['transcription'])
        client.subscribe(self.topics['llm']['response'])
        client.subscribe(self.topics['robot']['speaking'])
        
        self.log("📡 Logger connected to MQTT broker")
    
    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        timestamp = datetime.now()
        
        # Wake word detected
        if topic == self.topics['session']['wake_detected']:
            score = payload
            self.current_session = {
                "session_id": timestamp.strftime("%Y%m%d_%H%M%S"),
                "start_time": timestamp.isoformat(),
                "wake_word_score": float(score),
                "wake_word_time": timestamp.isoformat()
            }
            self.log("")
            self.log("🔊 " + "="*76)
            self.log(f"   WAKE WORD DETECTED - Score: {score}")
            self.log("   " + "="*76)
        
        # Session state change
        elif topic == self.topics['session']['state']:
            self.log(f"📋 Session state: {payload.upper()}")
            if payload == "idle" and self.current_session.get('session_id'):
                # Session ended - calculate duration
                if self.current_session.get('start_time'):
                    start = datetime.fromisoformat(self.current_session['start_time'])
                    duration = (timestamp - start).total_seconds()
                    self.current_session['end_time'] = timestamp.isoformat()
                    self.current_session['duration'] = duration
                    
                    self.log(f"⏱️  Session duration: {duration:.2f}s")
                    self.log("=" * 80)
                    
                    # Save to sessions list
                    self.all_sessions.append(self.current_session.copy())
                    self.save_session_json()
        
        # User transcription
        elif topic == self.topics['audio']['transcription']:
            self.current_session['user_question'] = payload
            self.current_session['question_time'] = timestamp.isoformat()
            
            self.log("")
            self.log(f"👤 USER: {payload}")
            self.log("")
        
        # LLM response
        elif topic == self.topics['llm']['response']:
            self.current_session['llm_response'] = payload
            self.current_session['response_time'] = timestamp.isoformat()
            
            # Calculate LLM response time
            if self.current_session.get('question_time'):
                q_time = datetime.fromisoformat(self.current_session['question_time'])
                llm_latency = (timestamp - q_time).total_seconds()
                self.current_session['llm_latency'] = llm_latency
                
                self.log(f"🤖 ASSISTANT ({llm_latency:.2f}s): {payload}")
            else:
                self.log(f"🤖 ASSISTANT: {payload}")
            self.log("")
        
        # TTS speaking events
        elif topic == self.topics['robot']['speaking']:
            if payload == "true":
                self.current_session['tts_start'] = timestamp.isoformat()
                self.log("🔊 TTS: Started speaking")
            else:
                self.current_session['tts_end'] = timestamp.isoformat()
                
                # Calculate TTS duration
                if self.current_session.get('tts_start'):
                    start = datetime.fromisoformat(self.current_session['tts_start'])
                    tts_duration = (timestamp - start).total_seconds()
                    self.current_session['tts_duration'] = tts_duration
                    
                    self.log(f"🔊 TTS: Finished ({tts_duration:.2f}s)")
                else:
                    self.log("🔊 TTS: Finished")
    
    def start(self):
        """Start the logger"""
        print("[ConvLogger] Starting conversation logger...")
        self.client.connect("localhost", 1883, 60)
        
        try:
            self.client.loop_forever()
        except KeyboardInterrupt:
            self.log("")
            self.log("=" * 80)
            self.log("LOGGER STOPPED")
            self.log("=" * 80)
            self.save_session_json()
            print(f"\n[ConvLogger] Total sessions logged: {len(self.all_sessions)}")
            print(f"[ConvLogger] Logs saved to: {self.log_file}")
            print(f"[ConvLogger] JSON saved to: {self.json_file}")

if __name__ == "__main__":
    logger = ConversationLogger()
    logger.start()
