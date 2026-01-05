#!/usr/bin/env python3

with open('cli.py', 'r') as f:
    content = f.read()

# Comment out intent detection API call
content = content.replace(
    'intent = await self._detect_intent(user_input)',
    '# intent = await self._detect_intent(user_input)  # Disabled - unnecessary API call'
)

content = content.replace(
    'print(f"DEBUG: Claude analysis: {intent}")',
    '# print(f"DEBUG: Claude analysis: {intent}")  # Disabled'
)

with open('cli.py', 'w') as f:
    f.write(content)

print("✅ Removed intent detection")
print("   - One less API call per message")