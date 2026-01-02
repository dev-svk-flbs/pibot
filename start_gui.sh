#!/bin/bash
# Start GUI on HDMI display
cd /home/saptapi/robot
source venv/bin/activate
export DISPLAY=:0
python modules/gui_display.py
