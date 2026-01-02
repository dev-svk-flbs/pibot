#!/bin/bash
# Set USB speaker volume to 90% (UACDemoV1.0)
# Find the card number dynamically since it changes on reboot
CARD=$(aplay -l | grep "UACDemoV1.0" | head -1 | cut -d: -f1 | awk '{print $2}')
if [ -n "$CARD" ]; then
    amixer -c $CARD set PCM 90%
    echo "Volume set to 90% on card $CARD"
else
    echo "USB speaker not found"
fi
