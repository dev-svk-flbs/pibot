#!/bin/bash
# Auto-start robot services on login

# Add this to ~/.bashrc or run manually on boot

cd /home/saptapi/robot
source venv/bin/activate

# Start mosquitto if not running
if ! pgrep -x "mosquitto" > /dev/null; then
    echo "Starting mosquitto..."
    mosquitto -d
    sleep 2
fi

# Check if services are already running
if pgrep -f "session_manager.py" > /dev/null; then
    echo "Robot services already running!"
    exit 0
fi

# Start all services in background
echo "Starting robot voice assistant..."

# Session Manager
nohup python modules/session_manager.py > logs/session.log 2>&1 &
echo "✓ Session Manager (PID: $!)"
sleep 1

# LLM Client  
nohup python modules/llm_client.py > logs/llm.log 2>&1 &
echo "✓ LLM Client (PID: $!)"
sleep 1

# TTS Output
nohup python modules/tts_output.py > logs/tts.log 2>&1 &
echo "✓ TTS Output (PID: $!)"
sleep 1

# Audio Input
nohup python modules/audio_input.py > logs/audio.log 2>&1 &
echo "✓ Audio Input (PID: $!)"
sleep 1

# Conversation Logger (optional)
nohup python modules/conversation_logger.py > logs/logger_sys.log 2>&1 &
echo "✓ Conversation Logger (PID: $!)"

echo ""
echo "All services started! Say 'Hey Jarvis' to begin."
echo ""
echo "To stop: pkill -f 'session_manager|llm_client|tts_output|audio_input|conversation_logger'"
