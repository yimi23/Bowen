#!/usr/bin/env python3

# Make BOWEN quiet
with open('cli.py', 'r') as f:
    content = f.read()

# Change to ERROR level (only show errors)
content = content.replace(
    'level=logging.INFO',
    'level=logging.ERROR'
)

content = content.replace(
    'level=logging.DEBUG',
    'level=logging.ERROR'
)

with open('cli.py', 'w') as f:
    f.write(content)

print("✅ Logging set to ERROR only")
print("   - Much quieter startup")