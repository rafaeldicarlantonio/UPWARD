#!/usr/bin/env python3
"""
Recursively fix indentation for nested blocks
"""
import ast
import sys

# Read the file
with open('/workspace/router/chat.py', 'r') as f:
    content = f.read()

# Try to parse and get syntax errors
try:
    compile(content, 'chat.py', 'exec')
    print("No syntax errors!")
    sys.exit(0)
except SyntaxError as e:
    print(f"SyntaxError at line {e.lineno}: {e.msg}")
    
    # Read lines
    with open('/workspace/router/chat.py', 'r') as f:
        lines = f.readlines()
    
    # If error is "expected an indented block after X"
    if "expected an indented block" in e.msg:
        # The previous line (e.lineno - 1) ends with ':' and next line needs indentation
        problem_line_idx = e.lineno - 1  # The line that triggered the error
        block_start_idx = e.lineno - 2    # The line with ':'
        
        if block_start_idx >= 0:
            block_line = lines[block_start_idx]
            block_indent = len(block_line) - len(block_line.lstrip())
            expected_indent = block_indent + 4
            
            # Find all lines that are part of this block and fix them
            idx = problem_line_idx
            while idx < len(lines):
                line = lines[idx]
                if not line.strip():  # Empty line
                    idx += 1
                    continue
                
                current_indent = len(line) - len(line.lstrip())
                
                # If this line is at or below the block indent, we're done
                if current_indent <= block_indent and line.strip():
                    break
                
                # If this line needs more indentation
                if current_indent < expected_indent and line.strip():
                    spaces_to_add = expected_indent - current_indent
                    lines[idx] = ' ' * spaces_to_add + line
                    print(f"Fixed line {idx + 1}: indent {current_indent} -> {expected_indent}")
                
                idx += 1
            
            # Write back
            with open('/workspace/router/chat.py', 'w') as f:
                f.writelines(lines)
            
            print(f"Fixed indentation issue at line {e.lineno}, please run again")
        else:
            print("Could not determine block start")
    else:
        print("Different type of syntax error")
