#!/bin/bash
# Run Phase 2 components in separate terminals

echo "=== Starting Phase 2 Components ==="
echo ""
echo "This script will guide you through running Phase 2 modules"
echo ""

# Check venv
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run from /home/saptapi/robot"
    exit 1
fi

echo "📋 Start these modules in separate terminals:"
echo ""
echo "Terminal 1 - Session Manager:"
echo "  cd /home/saptapi/robot && source venv/bin/activate && python modules/session_manager.py"
echo ""
echo "Terminal 2 - LLM Client:"
echo "  cd /home/saptapi/robot && source venv/bin/activate && python modules/llm_client.py"
echo ""
echo "Terminal 3 - TTS Output:"
echo "  cd /home/saptapi/robot && source venv/bin/activate && python modules/tts_output.py"
echo ""
echo "Terminal 4 - Audio Input:"
echo "  cd /home/saptapi/robot && source venv/bin/activate && python modules/audio_input.py"
echo ""
echo "Terminal 5 - Conversation Logger (OPTIONAL):"
echo "  cd /home/saptapi/robot && source venv/bin/activate && python modules/conversation_logger.py"
echo ""
