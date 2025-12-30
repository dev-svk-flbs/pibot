#!/bin/bash
# Robot System Monitor - Continuous status display

LOG_DIR="/home/saptapi/robot/logs"

while true; do
    clear
    echo "🤖 ROBOT SYSTEM MONITOR"
    echo "======================="
    date '+%Y-%m-%d %H:%M:%S'
    echo ""
    
    # Service status
    echo "📊 SERVICE STATUS:"
    echo "==================="
    services=("robot-wakeword" "robot-stt" "robot-session" "robot-llm" "robot-tts" "robot-logger")
    for service in "${services[@]}"; do
        if systemctl is-active --quiet "$service"; then
            echo "   ✅ $service"
        else
            echo "   ❌ $service (STOPPED)"
        fi
    done
    echo ""
    
    # Current session state
    echo "🎯 SESSION STATE:"
    echo "================="
    SESSION_STATE=$(mosquitto_sub -t "session/state" -C 1 -W 1 2>/dev/null || echo "unknown")
    case $SESSION_STATE in
        "idle")
            echo "   💤 IDLE - Waiting for wake word"
            ;;
        "active")
            echo "   👂 ACTIVE - Listening to user"
            ;;
        "speaking")
            echo "   🗣️  SPEAKING - Robot talking"
            ;;
        *)
            echo "   ❓ Unknown state"
            ;;
    esac
    echo ""
    
    # Recent wake word detections
    echo "🔔 WAKEWORD (last 5 lines):"
    echo "==========================="
    tail -5 "$LOG_DIR/wakeword.log" 2>/dev/null | sed 's/^/   /' || echo "   No log"
    echo ""
    
    # Recent transcriptions
    echo "🎙️  STT (last 3 lines):"
    echo "======================"
    tail -3 "$LOG_DIR/stt.log" 2>/dev/null | sed 's/^/   /' || echo "   No log"
    echo ""
    
    # Recent LLM responses
    echo "🧠 LLM (last 3 lines):"
    echo "====================="
    tail -3 "$LOG_DIR/llm.log" 2>/dev/null | sed 's/^/   /' || echo "   No log"
    echo ""
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Commands: Ctrl+C to exit | mosquitto_pub -t session/command -m cancel"
    
    sleep 2
done
