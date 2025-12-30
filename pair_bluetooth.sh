#!/bin/bash
# Simple Bluetooth Pairing Script

echo "=== Bluetooth Audio Setup ==="
echo ""
echo "Make sure your Bluetooth headset/speaker is:"
echo "  1. Turned ON"
echo "  2. In PAIRING mode (usually hold power button)"
echo ""
read -p "Press Enter when ready..."

echo ""
echo "Scanning for 10 seconds..."
echo ""

# Scan and show devices
(
  sleep 1
  echo "scan on"
  sleep 10
  echo "devices"
  echo "exit"
) | bluetoothctl

echo ""
echo "=== Available Devices ==="
bluetoothctl devices

echo ""
read -p "Enter the MAC address (e.g., AA:BB:CC:DD:EE:FF): " MAC

if [ -z "$MAC" ]; then
  echo "Error: No MAC address entered"
  exit 1
fi

echo ""
echo "Connecting to $MAC..."
echo ""

# Connect device
(
  echo "power on"
  echo "agent on"
  echo "default-agent"
  echo "pair $MAC"
  sleep 3
  echo "trust $MAC"
  sleep 1
  echo "connect $MAC"
  sleep 3
  echo "info $MAC"
  echo "exit"
) | bluetoothctl

echo ""
echo "=== Testing Audio ==="
sleep 2

# Try playing through default device
aplay test.wav

echo ""
read -p "Did you hear audio through Bluetooth? (y/n): " HEARD

if [ "$HEARD" = "y" ]; then
  echo ""
  echo "✓ Success! Bluetooth audio working!"
  echo "Device: $MAC"
else
  echo ""
  echo "Let's try specifying the Bluetooth device explicitly..."
  echo ""
  aplay -L | grep -i blue
  echo ""
  read -p "Enter the device name from above (or press Enter to skip): " DEVICE
  
  if [ ! -z "$DEVICE" ]; then
    aplay -D "$DEVICE" test.wav
  fi
fi
