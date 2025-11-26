#!/usr/bin/env python3
"""
Fix all indentation issues in chat.py by checking each try/except/if block
"""
import re

with open('/workspace/router/chat.py', 'r') as f:
    lines = f.readlines()

def get_indent(line):
    """Get the number of leading spaces"""
    return len(line) - len(line.lstrip(' '))

def needs_indent(prev_line):
    """Check if previous line needs next line to be indented"""
    stripped = prev_line.strip()
    return (stripped.endswith(':') and 
            not stripped.startswith('#') and
            stripped != ':')

# Fix indentation by checking consistency
fixed_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # If previous line ends with ':', ensure current line is indented more
    if i > 0 and needs_indent(lines[i-1]):
        prev_indent = get_indent(lines[i-1])
        curr_indent = get_indent(line)
        
        # Skip empty lines
        if line.strip():
            if curr_indent <= prev_indent:
                # Need to indent this line
                line = ' ' * (prev_indent + 4) + line.lstrip()
    
    fixed_lines.append(line)
    i += 1

# Write back
with open('/workspace/router/chat.py', 'w') as f:
    f.writelines(fixed_lines)

print("Fixed indentation issues")
