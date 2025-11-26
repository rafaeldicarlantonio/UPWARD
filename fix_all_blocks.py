#!/usr/bin/env python3
"""
Iteratively fix all indentation errors
"""
import subprocess
import sys

MAX_ITERATIONS = 50

for iteration in range(MAX_ITERATIONS):
    # Try to compile
    result = subprocess.run(
        ['python3', '-m', 'py_compile', '/workspace/router/chat.py'],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print(f"✓ Success after {iteration} iterations!")
        sys.exit(0)
    
    # Parse error
    error = result.stderr
    if 'IndentationError' not in error and 'SyntaxError' not in error:
        print(f"Unknown error: {error}")
        sys.exit(1)
    
    # Extract line number
    import re
    match = re.search(r'line (\d+)', error)
    if not match:
        print(f"Could not parse error: {error}")
        sys.exit(1)
    
    error_line = int(match.group(1))
    
    # Check if it's "expected an indented block"
    if 'expected an indented block' in error:
        # Extract the actual line number from "after X statement on line Y"
        match2 = re.search(r'on line (\d+)', error)
        if match2:
            block_start_line = int(match2.group(1))  # 1-indexed
        else:
            block_start_line = error_line - 1  # 1-indexed
        
        with open('/workspace/router/chat.py', 'r') as f:
            lines = f.readlines()
        
        block_start_idx = block_start_line - 1  # 0-indexed
        
        if block_start_idx < 0 or not lines[block_start_idx].rstrip().endswith(':'):
            print(f"Line {block_start_line} doesn't end with ':'")
            continue
        
        # Get indent of block start
        block_indent = len(lines[block_start_idx]) - len(lines[block_start_idx].lstrip())
        expected_indent = block_indent + 4
        
        # Find the block end (next line at same or less indent as block start)
        error_idx = error_line - 1  # 0-indexed
        i = error_idx
        fixed_count = 0
        
        while i < len(lines):
            line = lines[i]
            if not line.strip():  # Empty line
                i += 1
                continue
            
            curr_indent = len(line) - len(line.lstrip())
            
            # Check if we've exited the block
            stripped = line.strip()
            is_block_keyword = stripped.startswith(('except ', 'except:', 'finally:', 'elif ', 'else:'))
            
            if curr_indent <= block_indent and (is_block_keyword or curr_indent < block_indent):
                # We've reached a line that's part of the outer block
                if is_block_keyword and curr_indent == block_indent:
                    # This is the except/finally/else for our block
                    pass  # Don't break, this belongs to our block level
                else:
                    break
            
            # If this line needs more indentation
            if curr_indent < expected_indent and line.strip():
                spaces_needed = expected_indent - curr_indent
                lines[i] = ' ' * spaces_needed + line
                fixed_count += 1
            
            i += 1
        
        # Write back
        with open('/workspace/router/chat.py', 'w') as f:
            f.writelines(lines)
        
        print(f"Iteration {iteration + 1}: Fixed {fixed_count} lines after line {error_line}")
    
    elif 'unexpected indent' in error:
        # Line has too much indentation
        with open('/workspace/router/chat.py', 'r') as f:
            lines = f.readlines()
        
        problem_idx = error_line - 1
        if problem_idx >= len(lines):
            break
        
        line = lines[problem_idx]
        if problem_idx > 0:
            prev_line = lines[problem_idx - 1]
            prev_indent = len(prev_line) - len(prev_line.lstrip())
            
            # Reduce indent to match previous line's level
            lines[problem_idx] = ' ' * prev_indent + line.lstrip()
            
            with open('/workspace/router/chat.py', 'w') as f:
                f.writelines(lines)
            
            print(f"Iteration {iteration + 1}: Fixed unexpected indent at line {error_line}")
    else:
        print(f"Unhandled error type: {error}")
        break

print(f"❌ Failed after {MAX_ITERATIONS} iterations")
sys.exit(1)
