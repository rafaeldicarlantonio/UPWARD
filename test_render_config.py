#!/usr/bin/env python3
"""
Test script to diagnose Render deployment issues.
Run this to see which environment variables are missing.
"""

import os
import sys

print("=" * 80)
print("RENDER DEPLOYMENT DIAGNOSTIC")
print("=" * 80)
print()

# Required environment variables
REQUIRED = [
    "OPENAI_API_KEY",
    "SUPABASE_URL",
    "PINECONE_API_KEY",
    "PINECONE_INDEX",
    "PINECONE_EXPLICATE_INDEX",
    "PINECONE_IMPLICATE_INDEX",
]

print("Checking required environment variables:")
print("-" * 80)

missing = []
present = []

for var in REQUIRED:
    value = os.getenv(var)
    if value:
        # Show first/last 4 chars only for security
        if len(value) > 8:
            masked = f"{value[:4]}...{value[-4:]}"
        else:
            masked = "***"
        present.append(var)
        print(f"✅ {var:30} = {masked}")
    else:
        missing.append(var)
        print(f"❌ {var:30} = NOT SET")

print()
print("=" * 80)
print(f"Summary: {len(present)}/{len(REQUIRED)} required variables set")
print("=" * 80)

if missing:
    print()
    print("❌ MISSING VARIABLES:")
    for var in missing:
        print(f"   - {var}")
    print()
    print("These must be set in Render dashboard under Environment tab")
    sys.exit(1)
else:
    print()
    print("✅ All required variables are set!")
    print()
    print("Attempting to load config...")
    try:
        from config import load_config
        config = load_config()
        print("✅ Config loaded successfully!")
        print()
        print("Attempting to import app...")
        from main import app
        print("✅ App imported successfully!")
        print(f"   App title: {app.title}")
        print(f"   App version: {app.version}")
    except Exception as e:
        print(f"❌ Error loading config or app: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

print()
print("=" * 80)
print("🎉 DIAGNOSTIC PASSED - App should start successfully")
print("=" * 80)
