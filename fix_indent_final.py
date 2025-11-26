#!/usr/bin/env python3
"""
Fix indentation by manually parsing and fixing known issues
"""

with open('/workspace/router/chat.py', 'r') as f:
    lines = f.readlines()

# Known fixes based on the error patterns
fixes = [
    # Fix line 547: if should be at 8 spaces (inside main try)
    (546, lambda l: l.lstrip().startswith('if action == "block"'), '        '),
    
    # Fix lines 558-560: comments should be at 8 spaces
    (557, lambda l: '# -----------------------' in l, '        '),
    (558, lambda l: '# Autosave' in l, '        '),
    (559, lambda l: '# -----------------------' in l, '        '),
    
    # Fix line 561: try should be at 8 spaces
    (560, lambda l: l.lstrip().startswith('try:'), '        '),
    
    # Lines 562-591: inside try block, should be at 12 spaces
    # These currently have 8 spaces, need 12
    *[(i, lambda l: True, '            ') for i in range(561, 591)],
    
    # Line 592: except should be at 8 spaces
    (591, lambda l: l.lstrip().startswith('except Exception:'), '        '),
    
    # Line 593: inside except, should be at 12 spaces  
    (592, lambda l: 'autosave' in l, '            '),
    
    # Line 597: try should be at 8 spaces
    (596, lambda l: l.lstrip().startswith('try:'), '        '),
]

# Apply fixes - reindent lines that match
for line_idx, condition, new_indent in fixes:
    if line_idx < len(lines):
        line = lines[line_idx]
        if line.strip() and condition(line):  # Not empty and matches condition
            lines[line_idx] = new_indent + line.lstrip()

with open('/workspace/router/chat.py', 'w') as f:
    f.writelines(lines)

print("Applied fixes")
