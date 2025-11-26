#!/usr/bin/env python3
"""
Fix the main try block structure (lines 249-770)
All code inside should be at least 8 spaces
"""

with open('/workspace/router/chat.py', 'r') as f:
    lines = f.readlines()

# Main try block is at line 249 (index 248)
# Its except is at line 770 (index 769)
# Everything in between should be indented to at least 8 spaces

for i in range(249, min(769, len(lines))):  # Lines 250-769 (indices 249-768)
    line = lines[i]
    
    # Skip empty lines
    if not line.strip():
        continue
    
    current_indent = len(line) - len(line.lstrip())
    
    # If line starts with exactly 4 spaces, it should be at 8
    # BUT: except/finally/elif/else at 4 spaces are OK if they match outer blocks
    stripped = line.strip()
    
    # Check if it's a block-ending keyword at the wrong level
    is_block_end = stripped.startswith(('except ', 'except:', 'finally:', 'elif ', 'else:'))
    
    if current_indent == 4 and not is_block_end:
        # Add 4 spaces
        lines[i] = '    ' + line
        print(f"Fixed line {i+1}: {stripped[:60]}")

with open('/workspace/router/chat.py', 'w') as f:
    f.writelines(lines)

print("Done!")
