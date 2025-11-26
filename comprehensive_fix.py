#!/usr/bin/env python3
"""
Comprehensive fix: Add 4 spaces to all lines from 250-769 that start with exactly 4 spaces
These are all inside the main try block (line 249) which requires 8 spaces minimum
"""

with open('/workspace/router/chat.py', 'r') as f:
    lines = f.readlines()

# Main try block: line 249 (index 248) to except at line 770 (index 769)
# All content inside should be at least 8 spaces

fixed_count = 0
for i in range(249, min(770, len(lines))):
    line = lines[i]
    # If line starts with exactly 4 spaces followed by non-space
    if len(line) > 4 and line[:4] == '    ' and line[4] != ' ':
        # Add 4 more spaces
        lines[i] = '    ' + line
        fixed_count += 1
        if fixed_count <= 10:
            print(f"Line {i+1}: {line[4:50].strip()}")

print(f"\nFixed {fixed_count} lines in main try block")

with open('/workspace/router/chat.py', 'w') as f:
    f.writelines(lines)

# Now fix any nested blocks that need adjustment
print("\nFixing nested blocks...")
import subprocess

for iteration in range(20):
    result = subprocess.run(['python3', '-m', 'py_compile', '/workspace/router/chat.py'],
                          capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✓ Success after {iteration} additional fixes!")
        break
    
    error = result.stderr
    if 'expected an indented block' not in error:
        print(f"Different error: {error[:200]}")
        break
    
    # Extract line with the block starter
    import re
    match = re.search(r'line (\d+)', error)
    if not match:
        break
    
    error_line = int(match.group(1))
    
    # Find "on line X" which is the block starter
    match2 = re.search(r'on line (\d+)', error)
    block_line = int(match2.group(1)) if match2 else error_line - 1
    
    with open('/workspace/router/chat.py', 'r') as f:
        lines = f.readlines()
    
    if block_line < 1 or block_line > len(lines):
        break
    
    block_idx = block_line - 1
    block_indent = len(lines[block_idx]) - len(lines[block_idx].lstrip())
    target_indent = block_indent + 4
    
    # Fix lines after the block starter until we hit a dedent
    idx = error_line - 1
    fixed = 0
    while idx < len(lines) and fixed < 100:
        line = lines[idx]
        if not line.strip():
            idx += 1
            continue
        
        curr_indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        
        # Stop if we've dedented past the block
        if curr_indent < target_indent:
            if stripped.startswith(('except', 'finally', 'elif', 'else')):
                break
            elif curr_indent <= block_indent:
                break
        
        # Fix if under-indented
        if curr_indent < target_indent:
            lines[idx] = ' ' * target_indent + stripped + '\n'
            fixed += 1
        
        idx += 1
    
    with open('/workspace/router/chat.py', 'w') as f:
        f.writelines(lines)
    
    print(f"  Iteration {iteration + 1}: Fixed {fixed} lines after line {block_line}")

print("\nFinal validation...")
result = subprocess.run(['python3', '-m', 'py_compile', '/workspace/router/chat.py'],
                       capture_output=True, text=True)
if result.returncode == 0:
    print("✓✓✓ File is now valid!")
else:
    print(f"Still has errors:\n{result.stderr[:500]}")
