#!/usr/bin/env python3

with open('bowen_core.py', 'r') as f:
    content = f.read()

# Add to system prompt
cultural_context = '''

## CULTURAL AWARENESS:

Praise references movies, music, games, and culture. Engage naturally with these references.

**Known References:**
- "Wake up daddies home" = Iron Man (Tony Stark returning from Afghanistan)
- Iron Man/MCU fan
- Don't be overly cautious about pop culture references

When user makes cultural reference:
- ✅ Engage with it naturally
- ✅ Show you understand the reference
- ❌ Don't treat it as inappropriate
- ❌ Don't give generic "I can't help with that" responses
'''

# Find system prompt and add this
import re
pattern = r'(## CONTEXT ABOUT PRAISE:.*?)(\n\n|\Z)'

def add_culture(match):
    return match.group(1) + cultural_context + match.group(2)

content = re.sub(pattern, add_culture, content, flags=re.DOTALL)

with open('bowen_core.py', 'w') as f:
    f.write(content)

print("✅ Added cultural awareness to system prompt")