#!/bin/bash
# Bluetooth Audio Setup Guide for Raspberry Pi 5

echo "=== Bluetooth Audio Setup ==="
echo ""
echo "Step 1: Turn on your Bluetooth headset/speaker"
echo "Step 2: Make it discoverable (pairing mode)"
echo ""
echo "Press Enter when ready..."
read

echo ""
echo "Scanning for Bluetooth devices..."
echo "This will run for 15 seconds..."
echo ""

# Start bluetoothctl in scan mode
timeout 15s bluetoothctl <<EOF
power on
agent on
scan on
EOF

echo ""
echo "=== Devices Found ==="
bluetoothctl devices

echo ""
echo "Enter the MAC address of your device (format: XX:XX:XX:XX:XX:XX):"
read MAC_ADDRESS

echo ""
echo "Pairing with $MAC_ADDRESS..."

# Pair and connect
bluetoothctl <<EOF
power on
agent on
default-agent
pair $MAC_ADDRESS
trust $MAC_ADDRESS
connect $MAC_ADDRESS
exit
EOF

echo ""
echo "=== Testing Audio ==="
echo "Playing test.wav through Bluetooth..."
sleep 2

# Play test file
aplay /home/saptapi/robot/test.wav

echo ""
echo "Did you hear the audio? (y/n)"
read HEARD

if [ "$HEARD" = "y" ] || [ "$HEARD" = "Y" ]; then
    echo ""
    echo "✓ Bluetooth audio working!"
    echo ""
    echo "Device MAC: $MAC_ADDRESS"
    echo ""
    echo "To set as default audio output, run:"
    echo "  pactl set-default-sink bluez_sink.${MAC_ADDRESS//:/_}"
else
    echo ""
    echo "⚠ Audio not working. Try:"
    echo "1. Check headset is connected: bluetoothctl info $MAC_ADDRESS"
    echo "2. List audio sinks: pactl list sinks short"
    echo "3. Try connecting again: bluetoothctl connect $MAC_ADDRESS"
fi
