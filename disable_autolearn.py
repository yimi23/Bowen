#!/usr/bin/env python3
"""
Turn OFF autonomous learning by default
Make it opt-in only when user asks "what is X"
"""

with open('cli.py', 'r') as f:
    content = f.read()

# Find where autonomous_learner is called in process_message
# Comment it out by default

import re

# Find the autonomous learning section
pattern = r'(# Autonomous learning.*?\n.*?autonomous_learner.*?\n.*?\n.*?\n)'

def comment_out(match):
    lines = match.group(1).split('\n')
    commented = '\n'.join(['# ' + line if line.strip() and not line.strip().startswith('#') else line for line in lines])
    return f"""
# AUTONOMOUS LEARNING DISABLED BY DEFAULT
# Only triggers when user explicitly asks "what is X?"
# This prevents unnecessary API calls on every message
{commented}
"""

content = re.sub(pattern, comment_out, content, flags=re.DOTALL)

# Add explicit learning trigger
learning_trigger = '''
        # Explicit learning - ONLY when user asks
        learning_triggers = ['what is', 'what\\'s', 'explain', 'tell me about', 'define']
        if any(trigger in user_input.lower() for trigger in learning_triggers):
            # User is asking about something - learn it
            unknown_concepts = await self.autonomous_learner.detect_unknowns(user_input)
            if unknown_concepts:
                learned = await self.autonomous_learner.research_and_learn(unknown_concepts[:1])  # Learn only 1 concept
'''

# Add this before the Claude API call
claude_call_pattern = r'(# Get Claude response)'
content = re.sub(claude_call_pattern, learning_trigger + '\n        \\1', content)

with open('cli.py', 'w') as f:
    f.write(content)

print("✅ Disabled auto-learning")
print("   - Now only learns when you explicitly ask")
print("   - Saves money and time")