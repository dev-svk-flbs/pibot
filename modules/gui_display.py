#!/usr/bin/env python3
"""
JARVIS GUI Display - Minimal, elegant interface
Clean blue/grey/white theme with status indicators and live conversation display
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import paho.mqtt.client as mqtt
import yaml
import threading
import time

class JarvisGUI:
    def __init__(self):
        # Load MQTT config
        with open('config/mqtt.yaml', 'r') as f:
            mqtt_config = yaml.safe_load(f)
        self.mqtt_config = mqtt_config
        self.topics = mqtt_config['topics']
        
        # State
        self.state = "idle"
        self.blink_state = False
        
        # Colors - Tech corporate blue/grey/white
        self.bg_dark = "#1a1f2e"      # Dark blue-grey background
        self.bg_medium = "#2d3748"    # Medium grey
        self.accent_blue = "#4299e1"  # Bright blue
        self.text_primary = "#e2e8f0" # Light grey text
        self.text_secondary = "#a0aec0" # Medium grey text
        self.idle_color = "#4a5568"   # Grey for idle
        self.active_color = "#48bb78" # Green for active
        self.speaking_color = "#4299e1" # Blue for speaking
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("JARVIS")
        self.root.configure(bg=self.bg_dark)
        
        # Fullscreen on display 0
        try:
            self.root.attributes('-fullscreen', True)
        except:
            self.root.geometry("1024x768")
        
        self.setup_ui()
        self.setup_mqtt()
        
        # Start blink animation
        self.animate_blink()
    
    def setup_ui(self):
        """Create the GUI layout"""
        
        # Main container
        main_frame = tk.Frame(self.root, bg=self.bg_dark)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # ===== HEADER =====
        header_frame = tk.Frame(main_frame, bg=self.bg_dark)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Left side: JARVIS title
        title_frame = tk.Frame(header_frame, bg=self.bg_dark)
        title_frame.pack(side=tk.LEFT)
        
        tk.Label(
            title_frame,
            text="JARVIS",
            font=("Helvetica Neue", 60, "bold"),
            fg=self.accent_blue,
            bg=self.bg_dark
        ).pack(side=tk.LEFT)
        
        # Reset button (colorful accent)
        self.reset_btn = tk.Button(
            header_frame,
            text="RESET",
            font=("Helvetica Neue", 24, "bold"),
            bg="#f56565",
            fg="white",
            activebackground="#e53e3e",
            relief=tk.FLAT,
            padx=40,
            pady=20,
            cursor="hand2",
            command=self.reset_session
        )
        self.reset_btn.pack(side=tk.RIGHT)
        
        # ===== STATUS BAR =====
        status_frame = tk.Frame(main_frame, bg=self.bg_medium)
        status_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Status indicator
        self.status_indicator = tk.Canvas(
            status_frame,
            width=30,
            height=30,
            bg=self.bg_medium,
            highlightthickness=0
        )
        self.status_indicator.pack(side=tk.LEFT, padx=20, pady=15)
        self.status_circle = self.status_indicator.create_oval(5, 5, 25, 25, fill=self.idle_color, outline="")
        
        self.status_label = tk.Label(
            status_frame,
            text="IDLE - Waiting for wake word",
            font=("Helvetica Neue", 28, "bold"),
            fg=self.text_primary,
            bg=self.bg_medium
        )
        self.status_label.pack(side=tk.LEFT, padx=10, pady=15)
        
        # ===== CONVERSATION DISPLAY =====
        conv_frame = tk.Frame(main_frame, bg=self.bg_dark)
        conv_frame.pack(fill=tk.BOTH, expand=True)
        
        # Label
        tk.Label(
            conv_frame,
            text="CONVERSATION",
            font=("Helvetica Neue", 22),
            fg=self.text_secondary,
            bg=self.bg_dark
        ).pack(anchor=tk.W, pady=(0, 10))
        
        # Scrolled text area
        self.conversation_text = scrolledtext.ScrolledText(
            conv_frame,
            font=("Helvetica Neue", 20),
            bg=self.bg_medium,
            fg=self.text_primary,
            insertbackground=self.accent_blue,
            relief=tk.FLAT,
            padx=25,
            pady=25,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.conversation_text.pack(fill=tk.BOTH, expand=True)
        
        # Configure text tags for styling
        self.conversation_text.tag_config(
            "user", 
            foreground=self.active_color, 
            font=("Helvetica Neue", 20, "bold")
        )
        self.conversation_text.tag_config(
            "jarvis", 
            foreground=self.accent_blue, 
            font=("Helvetica Neue", 20)
        )
        self.conversation_text.tag_config(
            "timestamp", 
            foreground=self.text_secondary, 
            font=("Helvetica Neue", 16)
        )
        
        # Footer
        footer = tk.Label(
            main_frame,
            text="Press ESC to exit fullscreen",
            font=("Helvetica Neue", 12),
            fg=self.text_secondary,
            bg=self.bg_dark
        )
        footer.pack(pady=(10, 0))
        
        # ESC key to exit fullscreen
        self.root.bind("<Escape>", lambda e: self.root.attributes('-fullscreen', False))
    
    def setup_mqtt(self):
        """Connect to MQTT broker"""
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gui_display")
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        
        # Connect in background thread
        def connect_mqtt():
            broker = self.mqtt_config['mqtt']['broker']
            port = self.mqtt_config['mqtt']['port']
            self.mqtt_client.connect(broker, port, 60)
            self.mqtt_client.loop_start()
        
        mqtt_thread = threading.Thread(target=connect_mqtt, daemon=True)
        mqtt_thread.start()
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        """Subscribe to relevant topics"""
        client.subscribe(self.topics['session']['state'])
        client.subscribe(self.topics['session']['wake_detected'])
        client.subscribe(self.topics['audio']['transcription'])
        client.subscribe(self.topics['llm']['response'])
        self.add_log("System ready", "timestamp")
    
    def on_message(self, client, userdata, msg):
        """Handle MQTT messages"""
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        # Session state change
        if topic == self.topics['session']['state']:
            self.update_state(payload)
        
        # Wake word detected - just update status, don't log
        elif topic == self.topics['session']['wake_detected']:
            self.status_label.config(text="Wake word detected!", fg=self.accent_blue)
        
        # User transcription
        elif topic == self.topics['audio']['transcription']:
            self.add_log(f"YOU: {payload}", "user")
        
        # JARVIS response
        elif topic == self.topics['llm']['response']:
            self.add_log(f"JARVIS: {payload}", "jarvis")
            self.add_log("", "timestamp")  # Empty line for spacing
    
    def update_state(self, new_state):
        """Update UI based on session state"""
        self.state = new_state.lower()
        
        if self.state == "idle":
            self.status_label.config(text="IDLE - Waiting for wake word", fg=self.text_primary)
            self.status_indicator.itemconfig(self.status_circle, fill=self.idle_color)
        elif self.state == "active":
            self.status_label.config(text="LISTENING - Speak now", fg=self.text_primary)
            self.status_indicator.itemconfig(self.status_circle, fill=self.active_color)
        elif self.state == "speaking":
            self.status_label.config(text="SPEAKING - Do not interrupt", fg=self.text_primary)
            self.status_indicator.itemconfig(self.status_circle, fill=self.speaking_color)
    
    def add_log(self, message, tag="normal"):
        """Add message to conversation display"""
        self.conversation_text.config(state=tk.NORMAL)
        
        # Add timestamp for non-timestamp messages
        if tag != "timestamp" and message:
            timestamp = time.strftime("%H:%M:%S")
            self.conversation_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        
        self.conversation_text.insert(tk.END, message + "\n", tag)
        self.conversation_text.see(tk.END)  # Auto-scroll to bottom
        self.conversation_text.config(state=tk.DISABLED)
    
    def animate_blink(self):
        """Animate the status indicator blinking"""
        if self.state != "idle":
            # Blink indicator when active/speaking
            self.blink_state = not self.blink_state
            if self.blink_state:
                if self.state == "active":
                    color = self.active_color
                else:
                    color = self.speaking_color
                self.status_indicator.itemconfig(self.status_circle, fill=color)
            else:
                self.status_indicator.itemconfig(self.status_circle, fill=self.bg_dark)
        
        self.root.after(500, self.animate_blink)
    
    def reset_session(self):
        """Send reset command to MQTT"""
        self.mqtt_client.publish(self.topics['session']['command'], "reset")
        self.add_log("Session reset", "timestamp")
    
    def run(self):
        """Start the GUI"""
        self.root.mainloop()

if __name__ == "__main__":
    gui = JarvisGUI()
    gui.run()
