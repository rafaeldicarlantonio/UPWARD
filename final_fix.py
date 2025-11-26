#!/usr/bin/env python3
"""
Comprehensive indentation fix - process line by line and fix based on context
"""
import re

with open('/workspace/router/chat.py', 'r') as f:
    lines = f.readlines()

def get_indent(line):
    return len(line) - len(line.lstrip())

def should_indent_next(line):
    """Check if the next line should be indented"""
    stripped = line.strip()
    if not stripped or stripped.startswith('#'):
        return False
    return stripped.endswith(':')

# Track indentation stack
indent_stack = [0]  # Start with base indentation
i = 0

while i < len(lines):
    line = lines[i]
    stripped = line.strip()
    
    # Skip empty lines and comments at start
    if not stripped:
        i += 1
        continue
    
    current_indent = get_indent(line)
    
    # Check if this is a dedent keyword
    is_dedent = stripped.startswith(('except ', 'except:', 'finally:', 'elif ', 'else:'))
    
    if is_dedent and len(indent_stack) > 1:
        # Pop stack and match the try/if level
        indent_stack.pop()
        expected_indent = indent_stack[-1]
        if current_indent != expected_indent:
            lines[i] = ' ' * expected_indent + stripped + '\n'
            print(f"Line {i+1}: Fixed dedent keyword to {expected_indent} spaces")
        # This keyword starts a new block at current level
        indent_stack.append(expected_indent)
    
    # Check if next line should be indented
    if should_indent_next(line):
        indent_stack.append(current_indent + 4)
    
    i += 1

# Now do a second pass to fix content inside blocks
with open('/workspace/router/chat.py', 'w') as f:
    f.writelines(lines)

# Second pass: fix lines that are inside blocks but not indented enough
with open('/workspace/router/chat.py', 'r') as f:
    lines = f.readlines()

i = 0
while i < len(lines):
    if i == 0:
        i += 1
        continue
    
    prev_line = lines[i-1]
    line = lines[i]
    
    if not line.strip():
        i += 1
        continue
    
    prev_indent = get_indent(prev_line)
    curr_indent = get_indent(line)
    stripped = line.strip()
    
    # If previous line ends with ':', current line should be indented more
    if should_indent_next(prev_line):
        expected_indent = prev_indent + 4
        
        # Unless current line is a dedent keyword at the right level
        is_dedent = stripped.startswith(('except ', 'except:', 'finally:', 'elif ', 'else:'))
        if is_dedent:
            expected_indent = prev_indent
        
        if curr_indent < expected_indent and not is_dedent:
            lines[i] = ' ' * expected_indent + stripped + '\n'
            print(f"Line {i+1}: Indented to {expected_indent} spaces (after ':' on line {i})")
    
    i += 1

with open('/workspace/router/chat.py', 'w') as f:
    f.writelines(lines)

print("Done!")
