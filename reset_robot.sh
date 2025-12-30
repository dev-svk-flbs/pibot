#!/bin/bash
# Robot System Reset Script
# Stops all services, clears logs, and restarts the system

set -e

echo "🤖 ROBOT SYSTEM RESET"
echo "===================="
echo ""

# Define services
SERVICES=(
    "robot-wakeword"
    "robot-stt"
    "robot-session"
    "robot-llm"
    "robot-tts"
    "robot-logger"
)

# Stop all services
echo "🛑 Stopping all robot services..."
for service in "${SERVICES[@]}"; do
    echo "   Stopping $service..."
    sudo systemctl stop "$service" 2>/dev/null || echo "   ⚠️  $service not running"
done
echo "✓ All services stopped"
echo ""

# Archive old logs
echo "📋 Archiving logs..."
LOG_DIR="/home/saptapi/robot/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_DIR="$LOG_DIR/archive_$TIMESTAMP"

if [ -d "$LOG_DIR" ]; then
    mkdir -p "$ARCHIVE_DIR"
    
    # Move all .log files to archive
    for logfile in "$LOG_DIR"/*.log; do
        if [ -f "$logfile" ]; then
            mv "$logfile" "$ARCHIVE_DIR/" 2>/dev/null || true
        fi
    done
    
    echo "✓ Logs archived to: $ARCHIVE_DIR"
else
    echo "⚠️  Log directory not found, skipping..."
fi
echo ""

# Wait a moment
echo "⏳ Waiting 2 seconds..."
sleep 2
echo ""

# Start all services
echo "🚀 Starting all robot services..."
for service in "${SERVICES[@]}"; do
    echo "   Starting $service..."
    sudo systemctl start "$service"
done
echo "✓ All services started"
echo ""

# Wait for services to initialize
echo "⏳ Waiting 3 seconds for initialization..."
sleep 3
echo ""

# Check service status
echo "📊 Service Status:"
echo "=================="
for service in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "$service"; then
        echo "   ✅ $service - RUNNING"
    else
        echo "   ❌ $service - FAILED"
    fi
done
echo ""

# Show recent logs
echo "📋 Recent Logs:"
echo "==============="
echo ""
echo "--- Wakeword ---"
tail -5 "$LOG_DIR/wakeword.log" 2>/dev/null || echo "No log yet"
echo ""
echo "--- STT ---"
tail -5 "$LOG_DIR/stt.log" 2>/dev/null || echo "No log yet"
echo ""

echo "🎉 RESET COMPLETE!"
echo ""
echo "Tip: Use 'sudo systemctl status robot-*' to check all services"
echo "     Use 'tail -f $LOG_DIR/<service>.log' to monitor logs"
