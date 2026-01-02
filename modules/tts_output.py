#!/usr/bin/env python3
"""
TTS Output - Text-to-Speech using Piper (neural TTS)
Subscribes to llm/response and quiz/speak, converts to speech
"""

import paho.mqtt.client as mqtt
import yaml
import subprocess
import time
from datetime import datetime

def ts():
    """Timestamp for logs"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

class TTSOutput:
    def __init__(self):
        # Load MQTT config
        with open('config/mqtt.yaml', 'r') as f:
            mqtt_config = yaml.safe_load(f)
        self.topics = mqtt_config['topics']
        
        # Load TTS config
        with open('config/tts.yaml', 'r') as f:
            tts_config = yaml.safe_load(f)
        
        # TTS settings - configurable voice
        voice_name = tts_config.get('voice', 'en_US-lessac-low')
        self.model_path = f"piper_models/{voice_name}.onnx"
        self.config_path = f"piper_models/{voice_name}.onnx.json"
        self.length_scale = str(tts_config.get('length_scale', 0.75))
        
        # Auto-detect sample rate from model config
        import json
        with open(self.config_path, 'r') as f:
            model_config = json.load(f)
        self.sample_rate = model_config['audio']['sample_rate']
        
        print(f"[{ts()}] [TTSOutput] Using voice: {voice_name}")
        print(f"[{ts()}] [TTSOutput] Sample rate: {self.sample_rate} Hz")
        print(f"[{ts()}] [TTSOutput] Speed: {self.length_scale}x")
        
        # State
        self.is_speaking = False
        
        # MQTT
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="tts_output")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        print(f"[{ts()}] [TTSOutput] Initialized with Piper TTS")
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"[{ts()}] [TTSOutput] Connected to MQTT broker (rc={rc})")
        client.subscribe(self.topics['llm']['response'])
        client.subscribe(self.topics['quiz']['speak'])
    
    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        # Handle LLM response or quiz speech
        if topic in [self.topics['llm']['response'], self.topics['quiz']['speak']]:
            if payload.strip():
                self.speak(payload)
    
    def speak(self, text):
        """Convert text to speech using Piper - OPTIMIZED for low latency"""
        if self.is_speaking:
            print(f"[{ts()}] [TTSOutput] Already speaking, skipping...")
            return
        
        try:
            # Set speaking flag and publish IMMEDIATELY
            self.is_speaking = True
            self.client.publish(self.topics['robot']['speaking'], "true")
            
            # Truncate preview for logging
            preview = text[:50] + "..." if len(text) > 50 else text
            print(f"[{ts()}] [TTSOutput] Speaking: {preview}")
            
            # Measure total time
            start_time = time.time()
            
            # OPTIMIZED: Stream Piper output directly to aplay (no intermediate buffer)
            # This starts playback AS SOON AS first audio is generated
            piper_cmd = [
                "piper",
                "--model", self.model_path,
                "--config", self.config_path,
                "--length_scale", self.length_scale,
                "--output-raw"
            ]
            
            aplay_cmd = [
                "aplay", 
                "-D", "plughw:UACDemoV10,0", 
                "-r", str(self.sample_rate), 
                "-f", "S16_LE", 
                "-c", "1"
            ]
            
            # Pipeline: text -> piper -> aplay (streaming)
            piper_proc = subprocess.Popen(
                piper_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            aplay_proc = subprocess.Popen(
                aplay_cmd,
                stdin=piper_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Close piper stdout in parent to allow pipe to work
            piper_proc.stdout.close()
            
            # Send text to piper
            piper_proc.stdin.write(text.encode('utf-8'))
            piper_proc.stdin.close()
            
            # Wait for both processes to complete
            aplay_proc.wait()
            piper_proc.wait()
            
            total_time = time.time() - start_time
            print(f"[{ts()}] [TTSOutput] ✓ Complete in {total_time:.2f}s")
            
            # Small pause after speaking
            time.sleep(0.2)
            
        except Exception as e:
            print(f"[{ts()}] [TTSOutput] Error: {e}")
        
        finally:
            # Clear speaking flag
            self.is_speaking = False
            self.client.publish(self.topics['robot']['speaking'], "false")
            print(f"[{ts()}] [TTSOutput] Finished speaking")
    
    def start(self):
        """Start TTS output module"""
        print(f"[{ts()}] [TTSOutput] Starting with Piper neural TTS...")
        
        # Test piper
        print(f"[{ts()}] [TTSOutput] Testing Piper...")
        test_proc = subprocess.run(
            ["piper", "--model", self.model_path, "--config", self.config_path, "--output-raw"],
            input=b"TTS module ready",
            capture_output=True
        )
        
        if test_proc.returncode == 0:
            print(f"[{ts()}] [TTSOutput] ✓ Piper test successful")
        else:
            print(f"[{ts()}] [TTSOutput] ⚠ Piper test warning: {test_proc.stderr.decode()}")
        
        # Connect MQTT
        with open('config/mqtt.yaml', 'r') as f:
            mqtt_config = yaml.safe_load(f)
        broker = mqtt_config['mqtt']['broker']
        port = mqtt_config['mqtt']['port']
        
        self.client.connect(broker, port, 60)
        
        print(f"[{ts()}] [TTSOutput] Ready to speak!")
        self.client.loop_forever()
    
    def stop(self):
        """Stop TTS output"""
        print(f"[{ts()}] [TTSOutput] Stopping...")
        self.client.disconnect()

if __name__ == "__main__":
    tts = TTSOutput()
    try:
        tts.start()
    except KeyboardInterrupt:
        tts.stop()
