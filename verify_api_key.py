#!/usr/bin/env python3
"""Verify if the OpenRouter API key works"""

import os
import sys
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get('OPENROUTER_API_KEY')
api_url = os.environ.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1/chat/completions')
model = os.environ.get('OPENROUTER_MODEL', 'google/gemini-2.0-flash-001')

print("=" * 60)
print("OPENROUTER API KEY VERIFICATION")
print("=" * 60)

if not api_key:
    print("❌ ERROR: OPENROUTER_API_KEY not found in .env file")
    sys.exit(1)

print(f"\n✓ API Key found: {api_key[:20]}...")
print(f"✓ Key length: {len(api_key)} characters")

print("\n[Test 1] Attempting OpenRouter request setup...")
try:
    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': 'Say Hello only'}],
    }
    data = json.dumps(payload).encode('utf-8')
    print("✓ Request initialized successfully")
except Exception as e:
    print(f"❌ Request initialization failed: {e}")
    sys.exit(1)

print("\n[Test 2] Attempting to generate simple content...")
try:
    req = urllib.request.Request(
        api_url,
        data=data,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': os.environ.get('OPENROUTER_SITE_URL', 'http://localhost:5000'),
            'X-Title': os.environ.get('OPENROUTER_APP_NAME', 'AI Study Planner'),
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        parsed = json.loads(resp.read().decode('utf-8'))
    response_text = parsed.get('choices', [{}])[0].get('message', {}).get('content', '')
    print(f"✓ API call successful!")
    print(f"Response: {response_text}")
except Exception as e:
    error_str = str(e)
    print(f"❌ API call failed: {error_str}")
    
    if 'quota' in error_str.lower() or 'RESOURCE_EXHAUSTED' in error_str:
        print("\n🔴 ISSUE: QUOTA OR CREDIT LIMIT REACHED")
        print("   Your OpenRouter credits or model limits may be exhausted")
        print("   Check usage in OpenRouter dashboard")
        print("\n   SOLUTIONS:")
        print("   1. Add credits / check limits in OpenRouter")
        print("   2. Switch to another model in OPENROUTER_MODEL")
        print("   3. Add backup keys in OPENROUTER_API_KEYS")
    elif 'invalid' in error_str.lower() or 'unauthenticated' in error_str.lower():
        print("\n🔴 ISSUE: INVALID OR EXPIRED API KEY")
        print("   This API key is not valid")
        print("   Please generate a new one from OpenRouter")
    elif '401' in error_str or '403' in error_str:
        print("\n🔴 ISSUE: AUTHENTICATION FAILED")
        print("   Permission denied for this API key")
    else:
        print(f"\n🔴 ISSUE: {type(e).__name__}")
    
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ API KEY IS VALID AND WORKING!")
print("=" * 60)
