#!/usr/bin/env python3
"""
Test the graduated memory model
Simulates a conversation and shows what gets sent to the LLM
"""

import json
from pathlib import Path

# Simulate conversation memory
recent_qa = []
max_recent_qa = 3  # Last 3 full Q&A
max_question_history = 7  # 7 older questions only

def add_exchange(question, answer):
    """Add a Q&A exchange"""
    recent_qa.append({'q': question, 'a': answer, 'time': '2025-12-31'})

def show_what_llm_sees():
    """Show what gets sent to LLM"""
    print("\n" + "="*70)
    print("WHAT THE LLM SEES:")
    print("="*70)
    
    total_exchanges = len(recent_qa)
    
    if total_exchanges == 0:
        print("No previous context")
        return
    
    # Tier 2: Older questions (7 questions before the recent 3)
    recent_start = max(0, total_exchanges - max_recent_qa)
    older_start = max(0, recent_start - max_question_history)
    
    if older_start < recent_start:
        print("\n📚 TIER 2 - OLDER CONTEXT (questions only):")
        for i, qa in enumerate(recent_qa[older_start:recent_start], 1):
            print(f"   {i}. {qa['q']}")
    
    # Tier 1: Recent Q&A (last 3 full exchanges)
    print("\n💬 TIER 1 - RECENT CONVERSATION (full Q&A):")
    for i, qa in enumerate(recent_qa[recent_start:], 1):
        print(f"   Q{i}: {qa['q']}")
        print(f"   A{i}: {qa['a'][:60]}...")
        print()

# Simulate 12 exchanges
print("Simulating 12-question conversation...")
print("="*70)

exchanges = [
    ("What's 2 + 2?", "Two plus two equals four! Just like if you have two LEGO bricks..."),
    ("Tell me about cars", "Cars are amazing machines! They use engines to move fast..."),
    ("How fast is a Bugatti?", "A Bugatti Chiron can go over 260 mph! That's faster than..."),
    ("What about F1 cars?", "F1 cars are super fast racing cars that can go around 230 mph..."),
    ("How do rockets work?", "Rockets work by burning fuel that creates hot gases..."),
    ("What's in space?", "Space has planets, stars, galaxies, and black holes! It's huge..."),
    ("Can you build a rocket with LEGO?", "Yes! You can build an awesome LEGO rocket! Start with..."),
    ("What makes music?", "Music is made by vibrations that create sound waves! When you..."),
    ("How do drums work?", "Drums work by hitting a tight membrane that vibrates the air..."),
    ("What's math used for?", "Math helps us understand patterns, build things, and solve..."),
    ("Why do glasses help me see?", "Glasses use curved lenses to bend light rays so they focus..."),
    ("What's the fastest car?", "The fastest production car is the SSC Tuatara at 283 mph..."),
]

for i, (q, a) in enumerate(exchanges, 1):
    print(f"\nExchange {i}: '{q}'")
    add_exchange(q, a)
    
    # Show what LLM sees at key points
    if i in [3, 7, 12]:
        show_what_llm_sees()

print("\n" + "="*70)
print(f"TOTAL EXCHANGES: {len(recent_qa)}")
print(f"MEMORY LIMIT: {max_recent_qa + max_question_history} exchanges")
print("="*70)
print("\nMemory model explanation:")
print("- Always send last 3 Q&A pairs in FULL (6 messages)")
print("- Send 7 older QUESTIONS only (no answers) for context")
print("- Total: Max 10 exchanges, but only 13 messages to LLM")
print("- This saves tokens while maintaining conversation continuity!")
print("\nStored in: data/conversation_memory.json (survives reboots)")
