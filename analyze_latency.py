#!/usr/bin/env python3
"""
Analyze latency across the entire JARVIS pipeline
Tracks timing from wake word → transcription → LLM → TTS → audio playback
"""

import re
from datetime import datetime
from collections import defaultdict

def parse_timestamp(ts_str):
    """Parse HH:MM:SS.mmm timestamp to datetime"""
    try:
        # Handle timestamps like "10:50:27.303"
        return datetime.strptime(f"2025-12-31 {ts_str}", "%Y-%m-%d %H:%M:%S.%f")
    except:
        return None

def analyze_logs():
    """Analyze timing across all service logs"""
    
    # Read all logs
    with open('logs/wakeword.log', 'r') as f:
        wakeword_lines = f.readlines()
    with open('logs/stt.log', 'r') as f:
        stt_lines = f.readlines()
    with open('logs/llm.log', 'r') as f:
        llm_lines = f.readlines()
    with open('logs/tts.log', 'r') as f:
        tts_lines = f.readlines()
    
    # Extract timestamps for key events
    sessions = []
    
    # Find wake word detections
    wake_pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\].*DETECTED.*score=([\d.]+)')
    for line in wakeword_lines[-200:]:  # Last 200 lines
        match = wake_pattern.search(line)
        if match:
            ts = parse_timestamp(match.group(1))
            score = float(match.group(2))
            if ts:
                sessions.append({'wake_time': ts, 'wake_score': score})
    
    # Find transcription events
    transcribe_start_pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\].*Recording \(VAD-based\)')
    transcribe_end_pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\].*Recording stopped on silence \(([\d.]+)s\)')
    transcribe_result_pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\].*✅ \'(.+?)\' \(([\d.]+)s\)')
    
    stt_events = []
    for line in stt_lines[-100:]:
        start_match = transcribe_start_pattern.search(line)
        if start_match:
            stt_events.append({'type': 'start', 'time': parse_timestamp(start_match.group(1))})
        
        end_match = transcribe_end_pattern.search(line)
        if end_match:
            stt_events.append({'type': 'rec_end', 'time': parse_timestamp(end_match.group(1)), 'duration': float(end_match.group(2))})
        
        result_match = transcribe_result_pattern.search(line)
        if result_match:
            stt_events.append({'type': 'result', 'time': parse_timestamp(result_match.group(1)), 'text': result_match.group(2), 'process_time': float(result_match.group(3))})
    
    # Find LLM events
    llm_question_pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\].*Question: (.+)')
    llm_calling_pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\].*Calling gpt')
    llm_response_pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\].*Response received in ([\d.]+)s')
    
    llm_events = []
    for line in llm_lines[-100:]:
        q_match = llm_question_pattern.search(line)
        if q_match:
            llm_events.append({'type': 'question', 'time': parse_timestamp(q_match.group(1)), 'text': q_match.group(2)})
        
        call_match = llm_calling_pattern.search(line)
        if call_match:
            llm_events.append({'type': 'calling', 'time': parse_timestamp(call_match.group(1))})
        
        resp_match = llm_response_pattern.search(line)
        if resp_match:
            llm_events.append({'type': 'response', 'time': parse_timestamp(resp_match.group(1)), 'duration': float(resp_match.group(2))})
    
    # Find TTS events
    tts_speaking_pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\].*Speaking: (.+)')
    tts_piper_pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\].*Piper generated audio in ([\d.]+)s')
    tts_playback_pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2}\.\d{3})\].*Playback took ([\d.]+)s \(total: ([\d.]+)s\)')
    
    tts_events = []
    for line in tts_lines[-100:]:
        speak_match = tts_speaking_pattern.search(line)
        if speak_match:
            tts_events.append({'type': 'start', 'time': parse_timestamp(speak_match.group(1)), 'text': speak_match.group(2)[:50]})
        
        piper_match = tts_piper_pattern.search(line)
        if piper_match:
            tts_events.append({'type': 'piper', 'time': parse_timestamp(piper_match.group(1)), 'duration': float(piper_match.group(2))})
        
        play_match = tts_playback_pattern.search(line)
        if play_match:
            tts_events.append({'type': 'playback', 'time': parse_timestamp(play_match.group(1)), 'playback_time': float(play_match.group(2)), 'total': float(play_match.group(3))})
    
    # Analyze last complete session
    if len(sessions) >= 1 and len(stt_events) >= 3 and len(llm_events) >= 3 and len(tts_events) >= 3:
        # Get most recent complete interaction
        wake = sessions[-1]['wake_time']
        
        # Find corresponding STT events
        stt_start = None
        stt_end = None
        stt_result = None
        for evt in reversed(stt_events):
            if evt['type'] == 'result' and evt['time'] > wake and not stt_result:
                stt_result = evt
            elif evt['type'] == 'rec_end' and evt['time'] > wake and not stt_end:
                stt_end = evt
            elif evt['type'] == 'start' and evt['time'] > wake and not stt_start:
                stt_start = evt
        
        # Find corresponding LLM events
        llm_question = None
        llm_calling = None
        llm_response = None
        for evt in reversed(llm_events):
            if evt['type'] == 'response' and evt['time'] > wake and not llm_response:
                llm_response = evt
            elif evt['type'] == 'calling' and evt['time'] > wake and not llm_calling:
                llm_calling = evt
            elif evt['type'] == 'question' and evt['time'] > wake and not llm_question:
                llm_question = evt
        
        # Find corresponding TTS events
        tts_start = None
        tts_piper = None
        tts_playback = None
        for evt in reversed(tts_events):
            if evt['type'] == 'playback' and evt['time'] > wake and not tts_playback:
                tts_playback = evt
            elif evt['type'] == 'piper' and evt['time'] > wake and not tts_piper:
                tts_piper = evt
            elif evt['type'] == 'start' and evt['time'] > wake and not tts_start:
                tts_start = evt
        
        # Print analysis
        print("=" * 80)
        print("JARVIS PIPELINE LATENCY ANALYSIS (Most Recent Interaction)")
        print("=" * 80)
        print()
        
        if stt_start:
            delta_ms = (stt_start['time'] - wake).total_seconds() * 1000
            print(f"1. Wake Word Detected     → STT Recording Started: {delta_ms:7.1f} ms")
        
        if stt_end and stt_start:
            delta_ms = (stt_end['time'] - stt_start['time']).total_seconds() * 1000
            print(f"2. STT Recording Started  → Recording Stopped:     {delta_ms:7.1f} ms (VAD detected silence)")
        
        if stt_result and stt_end:
            delta_ms = (stt_result['time'] - stt_end['time']).total_seconds() * 1000
            print(f"3. Recording Stopped      → Transcription Done:    {delta_ms:7.1f} ms (Whisper processing)")
            if stt_result.get('text'):
                print(f"   Transcribed: \"{stt_result['text'][:60]}...\"")
        
        if llm_question and stt_result:
            delta_ms = (llm_question['time'] - stt_result['time']).total_seconds() * 1000
            print(f"4. Transcription Done     → LLM Received:          {delta_ms:7.1f} ms (MQTT latency)")
        
        if llm_response and llm_calling:
            delta_ms = (llm_response['time'] - llm_calling['time']).total_seconds() * 1000
            print(f"5. LLM Called             → LLM Response:          {delta_ms:7.1f} ms (GPT-4o-mini)")
        
        if tts_start and llm_response:
            delta_ms = (tts_start['time'] - llm_response['time']).total_seconds() * 1000
            print(f"6. LLM Response           → TTS Started:           {delta_ms:7.1f} ms (MQTT latency)")
        
        if tts_piper and tts_start:
            delta_ms = (tts_piper['time'] - tts_start['time']).total_seconds() * 1000
            print(f"7. TTS Started            → Piper Generated:       {delta_ms:7.1f} ms (Piper synthesis)")
        
        if tts_playback and tts_piper:
            delta_ms = (tts_playback['time'] - tts_piper['time']).total_seconds() * 1000
            print(f"8. Piper Generated        → Audio Started:         {delta_ms:7.1f} ms (aplay startup)")
        
        print()
        print("-" * 80)
        print("TOTAL LATENCY BREAKDOWN:")
        print("-" * 80)
        
        if stt_result and wake:
            total_stt = (stt_result['time'] - wake).total_seconds() * 1000
            print(f"Wake → Transcription Complete:  {total_stt:7.1f} ms")
        
        if llm_response and llm_question:
            print(f"LLM Processing:                 {llm_response.get('duration', 0) * 1000:7.1f} ms")
        
        if tts_playback and tts_start:
            total_tts = (tts_playback['time'] - tts_start['time']).total_seconds() * 1000
            print(f"TTS Generation + Playback:      {total_tts:7.1f} ms")
        
        if tts_playback and wake:
            total = (tts_playback['time'] - wake).total_seconds() * 1000
            print()
            print(f"{'TOTAL (Wake → Audio Playing):':.<40} {total:7.1f} ms ({total/1000:.2f} seconds)")
        
        print("=" * 80)
    else:
        print("Not enough log data to analyze a complete session.")
        print(f"Found: {len(sessions)} wake events, {len(stt_events)} STT events, {len(llm_events)} LLM events, {len(tts_events)} TTS events")

if __name__ == "__main__":
    analyze_logs()
