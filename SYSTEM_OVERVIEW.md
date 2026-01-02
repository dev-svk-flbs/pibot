# JARVIS Voice Assistant - System Overview

**Created:** January 2, 2026  
**Platform:** Raspberry Pi with dual USB microphones  
**Purpose:** Voice-activated AI assistant with wake word detection, speech recognition, LLM integration, and text-to-speech output

---

## Architecture Overview

This is a **microservices-based voice assistant** using **MQTT as the message bus** to coordinate between independent services. Each service runs as a systemd daemon and communicates via MQTT topics.

### Core Pipeline Flow

```
[Wake Word Detection] → [Session Manager] → [STT Service] → [LLM Client] → [TTS Output]
          ↓                    ↓                  ↓              ↓            ↓
      MQTT Broker ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← 
```

**Typical Interaction:**
1. User says "Hey Jarvis" → Wake word service publishes to `session/wake_detected`
2. Session Manager receives wake event, starts session, publishes to `session/state`
3. STT Service records 10 seconds of audio using `arecord` (ALSA), transcribes with `faster-whisper`
4. STT publishes transcribed text to `audio/transcription`
5. Session Manager forwards to LLM via `llm/request`
6. LLM Client calls OpenAI API, publishes response to `llm/response`
7. TTS Service receives response, generates speech with Piper, streams to `aplay`
8. Session Manager monitors for timeout (30s idle), ends session

---

## Directory Structure

```
/home/saptapi/robot/
├── config/                          # Configuration files
│   ├── mqtt.yaml                    # MQTT broker and topic definitions
│   ├── session.yaml                 # Session timeout settings (30s idle_timeout)
│   └── tts.yaml                     # TTS voice model configuration
│
├── modules/                         # Core service modules
│   ├── session_manager.py           # Session orchestration (systemd service)
│   ├── llm_client.py                # OpenAI GPT integration (systemd service)
│   ├── tts_output.py                # Piper TTS streaming output (systemd service)
│   ├── conversation_logger.py       # Logs Q&A to JSON files (systemd service)
│   └── gui_display.py               # Tkinter GUI (NOT YET IN USE - next focus)
│
├── systemd/                         # Service definition templates
│   ├── robot-session.service
│   ├── robot-llm.service
│   ├── robot-tts.service
│   ├── robot-logger.service
│   └── robot-gui.service            # GUI service (exists but may not be enabled)
│
├── logs/                            # Service logs (all stdout redirected here)
│   ├── wakeword.log
│   ├── stt.log
│   ├── session.log
│   ├── llm.log
│   ├── tts.log
│   ├── conversations_YYYY-MM-DD.json  # Daily conversation history
│   └── archive_YYYYMMDD_HHMMSS/       # Archived old conversations
│
├── data/
│   └── conversation_memory.json     # Persistent conversation memory (10 exchanges)
│
├── piper_models/                    # Neural TTS voice models
│   ├── en_US-lessac-medium.onnx
│   └── en_US-lessac-medium.onnx.json
│
├── recordings/                      # (Currently disabled for performance)
│   └── question_*.wav               # Debug recordings from STT
│
├── wakeword_alone.py                # Wake word detection (OpenWakeWord)
├── transcription_alone.py           # STT service (faster-whisper + arecord)
└── venv/                            # Python virtual environment
```

---

## Active Systemd Services

All services are managed via systemd and run as user `saptapi`. They auto-restart on failure.

| Service File | Script | Purpose | MQTT Subscriptions | MQTT Publications |
|--------------|--------|---------|-------------------|-------------------|
| `robot-wakeword.service` | `wakeword_alone.py` | Detects "Hey Jarvis" using OpenWakeWord | - | `session/wake_detected` |
| `robot-stt.service` | `transcription_alone.py` | Records and transcribes speech | `session/wake_detected` | `audio/transcription` |
| `robot-session.service` | `modules/session_manager.py` | Orchestrates conversation flow | `session/wake_detected`, `audio/transcription`, `llm/response` | `session/state`, `llm/request`, `session/command` |
| `robot-llm.service` | `modules/llm_client.py` | Calls OpenAI GPT-4o-mini | `llm/request`, `session/command` | `llm/response` |
| `robot-tts.service` | `modules/tts_output.py` | Speaks responses via Piper | `llm/response` | `robot/speaking` |
| `robot-logger.service` | `modules/conversation_logger.py` | Logs conversations to JSON | `audio/transcription`, `llm/response` | - |

**Service Management Commands:**
```bash
sudo systemctl status robot-wakeword
sudo systemctl restart robot-stt
journalctl -u robot-llm -f         # Follow logs in real-time
```

---

## Key Technical Details

### 1. Wake Word Detection (`wakeword_alone.py`)
- **Library:** `openwakeword`
- **Hardware:** First USB PnP Sound Device (48kHz)
- **Trigger Phrase:** "Hey Jarvis"
- **Threshold:** 0.1 (configurable)
- **Behavior:** Publishes wake score to MQTT, does NOT record audio itself

### 2. Speech-to-Text (`transcription_alone.py`)
- **Library:** `faster-whisper` (tiny model, int8 quantization)
- **Recording Method:** Native ALSA `arecord` command (most reliable on Pi)
  - Records directly at 16kHz (Whisper native rate)
  - Fixed 10-second window after wake word
  - Saves to `/tmp/recording.wav`
- **VAD:** Uses faster-whisper's built-in Silero VAD (vad_filter=True)
  - `min_silence_duration_ms: 500`
  - `speech_pad_ms: 200`
- **Hardware:** Second USB PnP Sound Device (or same if only one mic)
- **Performance Notes:** 
  - Audio archiving currently DISABLED for speed
  - Simplified from custom Python VAD to align with library best practices

### 3. Session Management (`modules/session_manager.py`)
- **Idle Timeout:** 30 seconds (increased from 15s to prevent premature closure)
- **State Machine:** `idle` → `active` → `thinking` → `responding` → `idle`
- **Responsibilities:**
  - Starts session on wake word
  - Routes transcription to LLM
  - Monitors for conversation end
  - Publishes session state changes

### 4. LLM Integration (`modules/llm_client.py`)
- **Model:** `gpt-4o-mini` via OpenAI API
- **System Prompt:** Tuned for a 9-year-old interested in cars, space, LEGO, and music
- **Memory:** Maintains last 10 conversation exchanges in `data/conversation_memory.json`
- **Optimization:** Publishes MQTT response BEFORE doing blocking I/O (logging/memory save)
- **Latency:** ~2-4 seconds per response

### 5. Text-to-Speech (`modules/tts_output.py`)
- **Engine:** Piper Neural TTS (ONNX models)
- **Voice:** `en_US-lessac-medium` (configurable in `config/tts.yaml`)
- **Streaming:** Pipes Piper output directly to `aplay` for minimal latency
- **Command:** `piper --model <model> --output-raw | aplay -r 22050 -f S16_LE -c 1`
- **Performance:** Streaming eliminates file I/O overhead

### 6. Conversation Logger (`modules/conversation_logger.py`)
- **Format:** Daily JSON files in `logs/conversations_YYYY-MM-DD.json`
- **Structure:**
```json
{
  "timestamp": "2026-01-02T23:51:49",
  "question": "Can you teach me the principles of Newtonian mechanics?",
  "answer": "Absolutely! Newtonian mechanics is all about how things move..."
}
```

---

## MQTT Topics Reference

**Defined in:** `config/mqtt.yaml`

| Topic | Publisher | Subscriber | Payload |
|-------|-----------|------------|---------|
| `session/wake_detected` | Wake Word | STT, Session | Wake score (float) |
| `session/state` | Session Manager | GUI | State: idle/active/thinking/responding |
| `session/command` | External | Session, LLM | Commands: reset, end |
| `audio/transcription` | STT | Session, Logger | Transcribed text (string) |
| `llm/request` | Session Manager | LLM | Question text (string) |
| `llm/response` | LLM | TTS, Logger, GUI | Answer text (string) |
| `robot/speaking` | TTS | GUI | Status: started/finished |

---

## GUI Display (PRELIMINARY - Next Focus Area)

**File:** `modules/gui_display.py`  
**Technology:** Python Tkinter  
**Status:** ✅ Code exists, 🟡 May not be actively running, 🔴 Needs development

### Current Features (from code inspection):
- **Fullscreen display** on HDMI output
- **Status indicator** showing system state (idle/listening/thinking/speaking)
- **Live conversation display** with scrolling history
- **Reset button** to end session
- **Color scheme:** Dark blue-grey theme (#1a1f2e background, #4299e1 accent)
- **MQTT Integration:** Subscribes to session state, transcription, and LLM response topics

### What the GUI Already Does:
1. Connects to MQTT broker
2. Listens for conversation updates
3. Displays real-time status changes
4. Shows Q&A history in scrolling text widget
5. Provides manual reset capability

### Next Session Goals:
- **Verify GUI service** is running: `systemctl status robot-gui.service`
- **Enhance visual feedback:**
  - Add animation for "listening" state
  - Show wake word confidence scores
  - Display LLM response streaming (if possible)
  - Add service health indicators (show if services are down)
- **System monitoring:**
  - CPU/memory usage graphs
  - MQTT connection status
  - Service uptime indicators
- **Debugging tools:**
  - View recent logs from each service
  - Manual service restart buttons
  - Audio level meters

### GUI Development Context:
The GUI can retrieve all necessary information by:
1. **Subscribing to MQTT topics** (already implemented)
2. **Reading log files** in `logs/` directory
3. **Checking systemd service status** via subprocess calls to `systemctl`
4. **Monitoring conversation history** from `logs/conversations_*.json`

---

## Performance Optimizations Applied

### Latency Reduction (9s → ~3-4s total):
1. ✅ LLM publishes to MQTT BEFORE saving to memory/logs
2. ✅ TTS streams via pipe instead of saving WAV files
3. ✅ STT disabled audio archiving (removed `cp` command)

### Audio Quality Improvements:
1. ✅ Removed custom Python VAD logic (was causing choppy audio)
2. ✅ Switched to native `arecord` for recording (eliminated Python buffer issues)
3. ✅ Let faster-whisper's Silero VAD handle silence detection internally
4. ✅ Simplified to fixed 10-second recording window

### Session Stability:
1. ✅ Increased idle timeout from 15s → 30s (prevents premature session close during transcription)

---

## Known Issues & Quirks

1. **Dual Microphone Setup:** System expects TWO USB microphones:
   - Mic 1: Wake word detection
   - Mic 2: STT recording
   - If only one mic exists, both services use it (may cause conflicts)

2. **Audio Archiving Disabled:** The `recordings/` folder functionality is commented out in `transcription_alone.py` for performance reasons. Re-enable for debugging if needed.

3. **GUI Service:** Check if `robot-gui.service` is enabled/running. May need to be started manually.

4. **MQTT Broker:** Must be running (`mosquitto`) before services start. Services will retry on connection failure.

---

## Development Environment

**Python Version:** 3.13  
**Virtual Environment:** `/home/saptapi/robot/venv/`  

**Key Dependencies:**
- `paho-mqtt` - MQTT client
- `faster-whisper` - Speech recognition
- `openwakeword` - Wake word detection
- `sounddevice` - Audio I/O (used by wake word)
- `openai` - GPT API client
- `pyyaml` - Config parsing
- `scipy` - Audio resampling (backup, not currently used)

**System Dependencies:**
- `arecord` / `aplay` (ALSA utilities)
- `piper` (Piper TTS binary in PATH)
- `mosquitto` (MQTT broker)

---

## Quick Start Guide for New Chat Session

1. **Check service status:**
   ```bash
   systemctl status robot-wakeword robot-stt robot-session robot-llm robot-tts robot-logger
   ```

2. **View live logs:**
   ```bash
   tail -f /home/saptapi/robot/logs/stt.log
   tail -f /home/saptapi/robot/logs/llm.log
   ```

3. **Restart a service:**
   ```bash
   sudo systemctl restart robot-stt
   ```

4. **Monitor MQTT messages:**
   ```bash
   mosquitto_sub -v -t '#'  # Subscribe to ALL topics
   ```

5. **Test the system:**
   - Say "Hey Jarvis"
   - Wait for beep/confirmation
   - Ask a question within 10 seconds
   - Listen for TTS response

---

## Context for GUI Development

The Tkinter GUI (`modules/gui_display.py`) is the **primary focus for the next session**. It already has:

- ✅ Basic layout and styling
- ✅ MQTT connectivity
- ✅ Conversation display
- ✅ Status indicators

**What needs work:**
- 🔧 Enhanced visual feedback and animations
- 🔧 Service health monitoring dashboard
- 🔧 Real-time log viewing
- 🔧 System metrics (CPU, memory, network)
- 🔧 Manual controls (restart services, clear memory, etc.)
- 🔧 Audio visualization (waveforms, volume meters)

**How to access data for GUI:**
- **Service status:** `subprocess.run(['systemctl', 'is-active', 'robot-stt'])`
- **Logs:** Read from `logs/*.log` files
- **Conversation history:** Parse `logs/conversations_*.json`
- **Real-time events:** Subscribe to MQTT topics (already implemented)
- **Memory state:** Read `data/conversation_memory.json`

The GUI runs on the HDMI display and should provide both **user-facing information** (conversation display) and **developer debugging tools** (service status, logs, metrics).

---

**End of System Overview**
