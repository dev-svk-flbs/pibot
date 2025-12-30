#!/bin/bash
# Stop all robot services gracefully

echo "Stopping robot voice assistant..."

# Kill all Python processes for robot modules
pkill -f "session_manager.py"
pkill -f "llm_client.py"
pkill -f "tts_output.py"
pkill -f "audio_input.py"
pkill -f "conversation_logger.py"

sleep 1

# Verify they're stopped
if pgrep -f "session_manager.py|llm_client.py|tts_output.py|audio_input.py|conversation_logger.py" > /dev/null; then
    echo "⚠ Some processes still running, forcing kill..."
    pkill -9 -f "session_manager.py"
    pkill -9 -f "llm_client.py"
    pkill -9 -f "tts_output.py"
    pkill -9 -f "audio_input.py"
    pkill -9 -f "conversation_logger.py"
fi

echo "✓ All robot services stopped"
