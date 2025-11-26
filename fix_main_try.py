#!/usr/bin/env python3
"""
Fix indentation for the main try block (lines 250-769)
All non-empty lines starting with exactly 4 spaces should be at 8 spaces
"""

with open('/workspace/router/chat.py', 'r') as f:
    lines = f.readlines()

for i in range(249, min(769, len(lines))):  # Lines 250-769 (0-indexed: 249-768)
    line = lines[i]
    # Check if line starts with exactly 4 spaces followed by a non-space character
    if line.startswith('    ') and len(line) > 4 and line[4] != ' ':
        # Add 4 spaces
        lines[i] = '    ' + line
        print(f"Fixed line {i+1}: {line[:50].strip()}...")

with open('/workspace/router/chat.py', 'w') as f:
    f.writelines(lines)

print("Done!")
