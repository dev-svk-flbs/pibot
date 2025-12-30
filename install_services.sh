#!/bin/bash
# Install robot systemd SYSTEM services

set -e

echo "=== Installing Robot Voice Assistant Services ==="
echo ""

echo "📋 Copying service files to /etc/systemd/system/ (requires sudo)..."
sudo cp systemd/*.service /etc/systemd/system/

echo "🔄 Reloading systemd..."
sudo systemctl daemon-reload

echo "✅ Enabling services..."
sudo systemctl enable robot-session robot-audio robot-llm robot-tts robot-logger

echo ""
echo "=== Installation Complete ==="
echo ""
echo "📋 Service Commands:"
echo ""
echo "Start all services:"
echo "  sudo systemctl start robot-session robot-audio robot-llm robot-tts robot-logger"
echo ""
echo "Stop all services:"
echo "  sudo systemctl stop robot-session robot-audio robot-llm robot-tts robot-logger"
echo ""
echo "Restart all services:"
echo "  sudo systemctl restart robot-session robot-audio robot-llm robot-tts robot-logger"
echo ""
echo "Check status:"
echo "  sudo systemctl status robot-*"
echo ""
echo "View logs:"
echo "  sudo journalctl -u robot-session -f"
echo "  tail -f logs/session.log logs/llm.log logs/tts.log"
echo ""
echo "Services will start automatically on boot!"
