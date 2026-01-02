#!/usr/bin/env python3
"""
LLM Client - GPT-5 nano integration for Q&A
Subscribes to llm/request, sends to OpenAI, publishes llm/response
"""

import paho.mqtt.client as mqtt
import yaml
import os
import time
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

def ts():
    """Timestamp for logs"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

class LLMClient:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Load MQTT config
        with open('config/mqtt.yaml', 'r') as f:
            mqtt_config = yaml.safe_load(f)
        self.topics = mqtt_config['topics']
        
        # OpenAI client
        api_key = os.getenv('OPENAI_API_KEY')
        model = os.getenv('OPENAI_MODEL', 'gpt-5-nano')
        
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in .env file")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        
        # GRADUATED MEMORY MODEL (Simple & Token Efficient)
        # Tier 1: Last 3 Q&A pairs (full detail) = 6 messages
        # Tier 2: Next 7 questions only (no answers) = 7 messages  
        # Total: Max 13 messages sent to LLM
        self.recent_qa = []  # List of {"q": str, "a": str, "time": str}
        self.max_recent_qa = 3  # Keep last 3 full Q&A exchanges
        self.max_question_history = 7  # Keep 7 older questions (no answers)
        
        # Persistent storage
        self.memory_file = Path("data/conversation_memory.json")
        self.memory_file.parent.mkdir(exist_ok=True)
        self.load_memory()
        
        # System prompt for kid-friendly assistant
        self.system_prompt = {
            "role": "system",
            "content": """You are JARVIS, a friendly and encouraging AI assistant for a creative 2nd-grade student.

ABOUT THE STUDENT:
- Grade 2 student who wears glasses
- Loves: LEGO building, creative crafting, cardboard replicas, painting
- Passionate about: Cars (F1, racing, fast cars, Bugatti, Rolls Royce, expensive cars)
- Interests: Space and astronomy, music (learning drums and guitar, makes tracks in GarageBand)
- Skills: Good at math, knows basic linear algebra and geometry concepts
- Learning style: Hands-on, creative, engineering-minded

YOUR TEACHING MISSION:
Primary Focus - Engineering & Science:
- Teach engineering principles through car mechanics, racing physics, aerodynamics
- Explain space concepts, astronomy, rocket science in simple terms
- Connect LEGO building to real engineering and architecture
- Use math to solve real problems (car speeds, distances, space calculations)
- Encourage problem-solving, critical thinking, and analytical reasoning

Character Development:
- Teach respect for elders and others
- Encourage politeness, gentleness, helpfulness, and caring for others
- Foster leadership qualities and teamwork
- Promote curiosity and lifelong learning

RESPONSE STYLE:
- 2-3 sentences max (unless explaining complex concepts)
- CRITICAL: Use PLAIN TEXT ONLY - NO markdown formatting like **bold**, _italics_, or ANY special characters
- CRITICAL: NO emojis (🚀, 😊, etc.) - text will be spoken aloud, not displayed
- Write naturally as if speaking: "LEGO Racing Track" not "**LEGO Racing Track**"
- Relate answers to his interests: cars, space, LEGO, music, building
- Use hands-on examples: "You could build this with LEGO!" or "Try painting this concept!"
- Connect math to real applications: car speeds, rocket trajectories, building measurements
- Be enthusiastic about his creativity and encourage more exploration
- Ask thought-provoking follow-up questions to develop critical thinking

Remember: He's smart, creative, and loves building things. Help him see how science and engineering 
power the cars and rockets he loves, and encourage him to keep creating, learning, and being kind!"""
        }
        
        # MQTT
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="llm_client")
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        
        print(f"[{ts()}] [LLMClient] Initialized with model: {self.model}")
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"[{ts()}] [LLMClient] Connected to MQTT broker (rc={rc})")
        client.subscribe(self.topics['llm']['request'])
        client.subscribe(self.topics['session']['state'])
    
    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        # Clear history when session returns to IDLE
        if topic == self.topics['session']['state']:
            if payload == "idle":
                if self.recent_qa:
                    print(f"[{ts()}] [LLMClient] Session ended, saving and clearing memory")
                    self.save_memory()
                    # Don't clear - keep persistent across sessions
        
        # Handle LLM request
        elif topic == self.topics['llm']['request']:
            if payload.strip():
                print(f"[{ts()}] [LLMClient] Question: {payload}")
                response = self.get_response(payload)
                
                # CRITICAL: Publish response IMMEDIATELY (before logging)
                self.mqtt_client.publish(self.topics['llm']['response'], response)
                print(f"[{ts()}] [LLMClient] Response published: {response[:80]}...")
    
    def load_memory(self):
        """Load conversation memory from persistent storage"""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                    self.recent_qa = data.get('recent_qa', [])
                    print(f"[{ts()}] [LLMClient] Loaded {len(self.recent_qa)} exchanges from memory")
            except Exception as e:
                print(f"[{ts()}] [LLMClient] Error loading memory: {e}")
                self.recent_qa = []
        else:
            self.recent_qa = []
    
    def save_memory(self):
        """Save conversation memory to persistent storage"""
        try:
            data = {
                'recent_qa': self.recent_qa,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.memory_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[{ts()}] [LLMClient] Error saving memory: {e}")
    
    def rotate_memory(self):
        """Rotate memory when it exceeds limits"""
        total_exchanges = len(self.recent_qa)
        max_total = self.max_recent_qa + self.max_question_history
        
        if total_exchanges > max_total:
            # Keep only the most recent exchanges
            self.recent_qa = self.recent_qa[-max_total:]
            print(f"[{ts()}] [LLMClient] Rotated memory, keeping last {max_total} exchanges")
    
    def build_context_messages(self):
        """Build graduated memory context for LLM"""
        messages = []
        
        total_exchanges = len(self.recent_qa)
        
        if total_exchanges == 0:
            return messages
        
        # Tier 1: Last 3 Q&A pairs (full detail)
        recent_start = max(0, total_exchanges - self.max_recent_qa)
        for qa in self.recent_qa[recent_start:]:
            messages.append({"role": "user", "content": qa['q']})
            messages.append({"role": "assistant", "content": qa['a']})
        
        # Tier 2: Older questions only (7 questions before the recent 3)
        older_start = max(0, recent_start - self.max_question_history)
        older_questions = []
        for qa in self.recent_qa[older_start:recent_start]:
            older_questions.append(qa['q'])
        
        if older_questions:
            # Insert as system context before recent Q&A
            context = "Earlier questions in this conversation: " + "; ".join(older_questions)
            messages.insert(0, {"role": "system", "content": context})
        
        return messages
    
    def clean_for_tts(self, text):
        """Remove markdown formatting and emojis for text-to-speech"""
        import re
        
        # Remove markdown bold/italic: **text** or __text__ or *text* or _text_
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold**
        text = re.sub(r'__(.+?)__', r'\1', text)      # __bold__
        text = re.sub(r'\*(.+?)\*', r'\1', text)      # *italic*
        text = re.sub(r'_(.+?)_', r'\1', text)        # _italic_
        
        # Remove emoji characters (Unicode ranges for common emojis)
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        text = emoji_pattern.sub('', text)
        
        return text.strip()
    
    
    def get_response(self, user_input):
        """Get response from GPT-4o-mini with graduated memory"""
        try:
            # Build messages with graduated memory
            messages = [self.system_prompt]
            
            # Add graduated context (recent Q&A + older questions)
            context_messages = self.build_context_messages()
            messages.extend(context_messages)
            
            # Add current question
            messages.append({"role": "user", "content": user_input})
            
            # Debug: Show what's being sent
            num_recent_qa = len([m for m in context_messages if m['role'] == 'user'])
            print(f"[{ts()}] [LLMClient] Context: {num_recent_qa} previous exchanges included")
            
            # Call OpenAI Chat Completion
            print(f"[{ts()}] [LLMClient] Calling {self.model}...")
            start_time = time.time()
            
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=200,  # ~150 words, allows complete 2-3 sentence responses
                temperature=0.7
            )
            
            elapsed = time.time() - start_time
            print(f"[{ts()}] [LLMClient] Response received in {elapsed:.2f}s")
            
            # Extract response
            assistant_message = completion.choices[0].message.content
            
            # Check if response is empty
            if not assistant_message or not assistant_message.strip():
                print(f"[{ts()}] [LLMClient] WARNING: Empty response")
                assistant_message = "I'm not sure how to answer that. Can you ask in a different way?"
            
            # Clean markdown formatting for TTS
            cleaned_message = self.clean_for_tts(assistant_message)
            
            # Add to memory (store AFTER returning response for speed)
            self.recent_qa.append({
                'q': user_input,
                'a': cleaned_message,
                'time': datetime.now().isoformat()
            })
            
            # Return immediately, do memory management asynchronously
            return cleaned_message
            
        except Exception as e:
            error_msg = f"Sorry, I had trouble thinking of an answer."
            print(f"[{ts()}] [LLMClient] Error: {e}")
            return error_msg
        finally:
            # Do memory rotation and save in background (non-blocking)
            try:
                self.rotate_memory()
                self.save_memory()
            except:
                pass  # Don't let memory save errors block responses
    
    def start(self):
        """Start the LLM client"""
        print(f"[{ts()}] [LLMClient] Starting...")
        
        # Connect MQTT
        with open('config/mqtt.yaml', 'r') as f:
            mqtt_config = yaml.safe_load(f)
        broker = mqtt_config['mqtt']['broker']
        port = mqtt_config['mqtt']['port']
        
        self.mqtt_client.connect(broker, port, 60)
        
        print(f"[{ts()}] [LLMClient] Ready to answer questions!")
        self.mqtt_client.loop_forever()
    
    def stop(self):
        """Stop the LLM client"""
        print(f"[{ts()}] [LLMClient] Stopping...")
        self.mqtt_client.disconnect()

if __name__ == "__main__":
    llm = LLMClient()
    try:
        llm.start()
    except KeyboardInterrupt:
        llm.stop()
