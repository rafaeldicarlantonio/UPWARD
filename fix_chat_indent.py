#!/usr/bin/env python3
"""
Fix specific indentation issues in router/chat.py
"""

with open('/workspace/router/chat.py', 'r') as f:
    lines = f.readlines()

# Fix known indentation issues
fixes = [
    # Line 547: if action == "block" - should be at 8 spaces (inside main try at line 249)
    (546, '            if action == "block":\n', '        if action == "block":\n'),
    
    # Lines 558-560: comments should be at 8 spaces
    (557, '            # -----------------------\n', '        # -----------------------\n'),
    (558, '            # Autosave (non-fatal) with robust fallback\n', '        # Autosave (non-fatal) with robust fallback\n'),
    (559, '            # -----------------------\n', '        # -----------------------\n'),
    
    # Line 561: try should be at 8 spaces
    (560, '        try:\n', '        try:\n'),  # Already correct
    
    # Lines 562-591: content inside try block should be at 12 spaces
    (561, '        # Prefer LLM-provided autosave candidates\n', '            # Prefer LLM-provided autosave candidates\n'),
    (562, '        candidates = (draft.get("autosave_candidates") or []).copy()\n', '            candidates = (draft.get("autosave_candidates") or []).copy()\n'),
    (564, '        # If none, derive from USER + ASSISTANT + small CONTEXT sample\n', '            # If none, derive from USER + ASSISTANT + small CONTEXT sample\n'),
    (565, '        if not candidates:\n', '            if not candidates:\n'),
]

# Apply fixes
for line_num, old, new in fixes:
    if line_num < len(lines) and lines[line_num] == old:
        lines[line_num] = new
        print(f"Fixed line {line_num + 1}")

# Write back
with open('/workspace/router/chat.py', 'w') as f:
    f.writelines(lines)

print("Done!")
