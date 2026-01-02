#!/usr/bin/env python3
"""
JARVIS GUI Display - Kid-Friendly Bold Interface
"""

import tkinter as tk
from tkinter import scrolledtext
import paho.mqtt.client as mqtt
import yaml
import threading
from datetime import datetime

class JarvisGUI:
    def __init__(self):
        with open('config/mqtt.yaml', 'r') as f:
            mqtt_config = yaml.safe_load(f)
        self.mqtt_config = mqtt_config
        self.topics = mqtt_config['topics']
        
        self.state = "idle"
        self.current_step = ""
        self.animation_dots = 0
        self.animation_running = False
        
        self.bg_dark = "#0a0e1a"
        self.bg_card = "#1a2332"
        self.neon_cyan = "#00ffff"
        self.neon_green = "#00ff88"
        self.neon_purple = "#cc00ff"
        self.neon_blue = "#0099ff"
        self.neon_yellow = "#ffff00"
        self.text_white = "#ffffff"
        self.text_dim = "#8899aa"
        
        self.root = tk.Tk()
        self.root.title("JARVIS")
        self.root.configure(bg=self.bg_dark)
        self.root.config(cursor="none")
        
        try:
            self.root.attributes('-fullscreen', True)
        except:
            self.root.geometry("1024x768")
        
        self.setup_ui()
        self.setup_mqtt()
        self.animate_status()
        self.update_clock()
    
    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg=self.bg_dark)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
        
        # ===== TOP BAR: Title, Status, Clock, Buttons =====
        header_frame = tk.Frame(main_frame, bg=self.bg_dark)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # JARVIS title - LEFT
        self.title_label = tk.Label(header_frame, text="J A R V I S", font=("Arial Black", 60, "bold"), fg=self.neon_cyan, bg=self.bg_dark)
        self.title_label.pack(side=tk.LEFT)
        
        # RIGHT SIDE: Buttons + Status + Clock
        right_frame = tk.Frame(header_frame, bg=self.bg_dark)
        right_frame.pack(side=tk.RIGHT, padx=20)
        
        # Compact status indicator
        self.status_label = tk.Label(right_frame, text="● IDLE", font=("Arial Black", 26, "bold"), fg=self.text_dim, bg=self.bg_dark)
        self.status_label.pack(side=tk.TOP, anchor=tk.E)
        
        # Clock
        self.clock_label = tk.Label(right_frame, text="00:00:00", font=("Arial", 22), fg=self.text_dim, bg=self.bg_dark)
        self.clock_label.pack(side=tk.TOP, anchor=tk.E, pady=(5, 0))
        
        # ===== MIDDLE STATUS BAR: Current Activity =====
        status_bar = tk.Frame(main_frame, bg=self.bg_card, highlightthickness=2, highlightbackground=self.neon_cyan)
        status_bar.pack(fill=tk.X, pady=(0, 10))
        
        self.activity_label = tk.Label(
            status_bar,
            text="Ready - Say 'Hey Jarvis' to start",
            font=("Arial", 24),
            fg=self.text_dim,
            bg=self.bg_card,
            pady=8
        )
        self.activity_label.pack()
        
        # ===== CONVERSATION DISPLAY =====
        conv_card = tk.Frame(main_frame, bg=self.bg_card, highlightthickness=3, highlightbackground=self.neon_cyan)
        conv_card.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(conv_card, text="CONVERSATION", font=("Arial Black", 26, "bold"), fg=self.neon_cyan, bg=self.bg_card, anchor=tk.W, padx=20, pady=8).pack(fill=tk.X)
        
        # Fill screen width, rely on natural wrapping
        self.conversation_text = scrolledtext.ScrolledText(
            conv_card, 
            font=("Arial", 30),  # Slightly smaller font for better fit
            bg=self.bg_dark, 
            fg=self.text_white, 
            insertbackground=self.neon_cyan, 
            relief=tk.FLAT, 
            padx=20,
            pady=15, 
            wrap=tk.WORD,
            state=tk.DISABLED, 
            borderwidth=0,
            highlightthickness=0
        )
        self.conversation_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        self.conversation_text.tag_config("user", foreground=self.neon_green, font=("Arial Black", 34, "bold"))
        self.conversation_text.tag_config("jarvis", foreground=self.neon_cyan, font=("Arial", 30))
        self.conversation_text.tag_config("timestamp", foreground=self.text_dim, font=("Arial", 20))
        
        self.root.bind("<Escape>", lambda e: self.root.attributes('-fullscreen', False))
    
    def setup_mqtt(self):
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gui_display")
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        
        def connect_mqtt():
            broker = self.mqtt_config['mqtt']['broker']
            port = self.mqtt_config['mqtt']['port']
            self.mqtt_client.connect(broker, port, 60)
            self.mqtt_client.loop_start()
        
        mqtt_thread = threading.Thread(target=connect_mqtt, daemon=True)
        mqtt_thread.start()
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        client.subscribe(self.topics['session']['state'])
        client.subscribe(self.topics['session']['wake_detected'])
        client.subscribe(self.topics['audio']['transcription'])
        client.subscribe(self.topics['llm']['response'])
        self.add_log("System ready", "timestamp")
    
    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        if topic == self.topics['session']['state']:
            self.update_state(payload)
        elif topic == self.topics['session']['wake_detected']:
            self.show_step("wake", "Wake word detected!")
        elif topic == self.topics['audio']['transcription']:
            self.add_log(f"YOU: {payload}", "user")
        elif topic == self.topics['llm']['response']:
            self.add_log(f"JARVIS: {payload}", "jarvis")
            self.add_log("", "timestamp")
    
    def update_state(self, new_state):
        self.state = new_state.lower()
        
        if self.state == "idle":
            self.show_step("idle", "Ready - Say 'Hey Jarvis' to start")
            self.animation_running = False
        elif self.state == "active":
            self.show_step("recording", "Recording your question")
            self.animation_running = True
        elif self.state == "transcribing":
            self.show_step("transcribing", "Converting speech to text")
            self.animation_running = True
        elif self.state == "thinking":
            self.show_step("thinking", "Asking the AI")
            self.animation_running = True
        elif self.state == "speaking":
            self.show_step("speaking", "Speaking the answer")
            self.animation_running = True
    
    def show_step(self, step_type, message):
        if step_type == "idle":
            self.status_label.config(text="● IDLE", fg=self.text_dim)
            self.title_label.config(fg=self.neon_cyan)
            self.activity_label.config(text=message, fg=self.text_dim)
        elif step_type == "wake":
            self.status_label.config(text="● WAKE!", fg=self.neon_yellow)
            self.title_label.config(fg=self.neon_yellow)
            self.activity_label.config(text="Wake word detected!", fg=self.neon_yellow)
        elif step_type == "recording":
            self.status_label.config(text="● RECORDING", fg=self.neon_green)
            self.title_label.config(fg=self.neon_green)
            self.activity_label.config(text=message, fg=self.neon_green)
        elif step_type == "transcribing":
            self.status_label.config(text="● TRANSCRIBING", fg=self.neon_purple)
            self.title_label.config(fg=self.neon_purple)
            self.activity_label.config(text=message, fg=self.neon_purple)
        elif step_type == "thinking":
            self.status_label.config(text="● THINKING", fg=self.neon_purple)
            self.title_label.config(fg=self.neon_purple)
            self.activity_label.config(text=message, fg=self.neon_purple)
        elif step_type == "speaking":
            self.status_label.config(text="● SPEAKING", fg=self.neon_blue)
            self.title_label.config(fg=self.neon_blue)
            self.activity_label.config(text=message, fg=self.neon_blue)
    
    def add_log(self, message, tag="normal"):
        self.conversation_text.config(state=tk.NORMAL)
        if tag in ["user", "jarvis"] and message:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.conversation_text.insert(tk.END, f"[{timestamp}]\n", "timestamp")
        self.conversation_text.insert(tk.END, message + "\n", tag)
        self.conversation_text.see(tk.END)
        self.conversation_text.config(state=tk.DISABLED)
    
    def animate_status(self):
        if self.animation_running:
            self.animation_dots = (self.animation_dots % 3) + 1
            dots = "." * self.animation_dots
            
            # Animate both status label and activity label
            current_text = self.status_label.cget("text")
            base_text = current_text.rstrip(".")
            self.status_label.config(text=base_text + dots)
            
            current_activity = self.activity_label.cget("text")
            base_activity = current_activity.rstrip(".")
            self.activity_label.config(text=base_activity + dots)
        
        self.root.after(500, self.animate_status)
    
    def update_clock(self):
        current_time = datetime.now().strftime("%H:%M:%S")
        self.clock_label.config(text=current_time)
        self.root.after(1000, self.update_clock)
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    gui = JarvisGUI()
    gui.run()
