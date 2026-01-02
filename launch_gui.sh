#!/bin/bash
# Simple script to launch JARVIS GUI
cd /home/saptapi/robot
xinit /home/saptapi/robot/venv/bin/python /home/saptapi/robot/modules/gui_display.py -- :0 vt7
