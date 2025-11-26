#!/usr/bin/env python3
"""
Fix indentation in chat.py by using autopep8
"""
import subprocess
import sys

# Use autopep8 to fix indentation
result = subprocess.run(
    ['python3', '-m', 'autopep8', '--in-place', '--select=E1,W1', '/workspace/router/chat.py'],
    capture_output=True,
    text=True
)

if result.returncode != 0:
    print(f"autopep8 failed: {result.stderr}", file=sys.stderr)
    sys.exit(1)

print("Fixed indentation in chat.py")
