#!/usr/bin/env python3
"""
LLM Client - GPT-5 nano integration for Q&A
Subscribes to llm/request, sends to OpenAI, publishes llm/response
"""

import paho.mqtt.client as mqtt
import yaml
import os
import time
from dotenv import load_dotenv
from openai import OpenAI

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
        
        # Conversation history with graduated memory
        self.conversation_history = []  # Recent full messages
        self.summary = ""  # Summary of older conversation
        self.max_recent = 6  # Keep last 6 exchanges full
        self.max_total = 20  # Summarize when exceeding 20 exchanges
        
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
        
        print(f"[LLMClient] Initialized with model: {self.model}")
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"[LLMClient] Connected to MQTT broker (rc={rc})")
        client.subscribe(self.topics['llm']['request'])
        client.subscribe(self.topics['session']['state'])
    
    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        # Clear history when session returns to IDLE
        if topic == self.topics['session']['state']:
            if payload == "idle":
                if self.conversation_history:
                    print("[LLMClient] Session ended, clearing conversation history")
                    self.conversation_history = []
        
        # Handle LLM request
        elif topic == self.topics['llm']['request']:
            if payload.strip():
                print(f"[LLMClient] Question: {payload}")
                response = self.get_response(payload)
                print(f"[LLMClient] Response: {response}")
                
                # Publish response
                self.mqtt_client.publish(self.topics['llm']['response'], response)
    
    def get_response(self, user_input):
        """Get response from GPT-5 nano"""
        try:
            # Build messages with graduated memory
            messages = [self.system_prompt]
            
            # Add summary if exists
            if self.summary:
                messages.append({"role": "system", "content": f"Previous conversation summary: {self.summary}"})
            
            # Add recent full history
            messages.extend(self.conversation_history)
            
            # Add current question
            messages.append({"role": "user", "content": user_input})
            
            # Call OpenAI Chat Completion (standard, fast)
            print(f"[LLMClient] Calling {self.model}...")
            start_time = time.time()
            
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=100,  # Shorter responses = faster TTS
                temperature=0.7
            )
            
            elapsed = time.time() - start_time
            print(f"[LLMClient] Response received in {elapsed:.2f}s")
            
            # Extract response
            assistant_message = completion.choices[0].message.content
            
            # Check if response is empty
            if not assistant_message or not assistant_message.strip():
                print(f"[LLMClient] WARNING: Empty response")
                assistant_message = "I'm not sure how to answer that. Can you ask in a different way?"
            
            # Add to conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": assistant_message})
            
            # Graduated memory: summarize old exchanges
            num_exchanges = len(self.conversation_history) // 2
            if num_exchanges > self.max_total:
                # Keep recent exchanges, summarize old ones
                recent = self.conversation_history[-self.max_recent * 2:]
                old = self.conversation_history[:-self.max_recent * 2]
                
                # Simple summarization: just mention topics
                topics = []
                for i in range(0, len(old), 2):
                    if i < len(old):
                        q = old[i]['content'][:50]
                        topics.append(q)
                
                self.summary = f"Earlier we discussed: {', '.join(topics[:5])}"
                self.conversation_history = recent
                print(f"[LLMClient] Summarized {len(old)//2} old exchanges")
            
            return assistant_message
            
        except Exception as e:
            error_msg = f"Sorry, I had trouble thinking of an answer. Error: {str(e)}"
            print(f"[LLMClient] Error: {e}")
            return error_msg
    
    def start(self):
        """Start the LLM client"""
        print("[LLMClient] Starting...")
        
        # Connect MQTT
        with open('config/mqtt.yaml', 'r') as f:
            mqtt_config = yaml.safe_load(f)
        broker = mqtt_config['mqtt']['broker']
        port = mqtt_config['mqtt']['port']
        
        self.mqtt_client.connect(broker, port, 60)
        
        print("[LLMClient] Ready to answer questions!")
        self.mqtt_client.loop_forever()
    
    def stop(self):
        """Stop the LLM client"""
        print("[LLMClient] Stopping...")
        self.mqtt_client.disconnect()

if __name__ == "__main__":
    llm = LLMClient()
    try:
        llm.start()
    except KeyboardInterrupt:
        llm.stop()
