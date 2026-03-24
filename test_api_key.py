import os
from dotenv import load_dotenv
import json
import urllib.request
import urllib.error

load_dotenv(override=True)
api_key = os.environ.get('OPENROUTER_API_KEY')
api_url = os.environ.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1/chat/completions')
model = os.environ.get('OPENROUTER_MODEL', 'google/gemini-2.0-flash-001')

print(f"Testing API key starting with: {api_key[:10]}..." if api_key else "No API key found")

try:
    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': 'Hello'}]
    }
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': os.environ.get('OPENROUTER_SITE_URL', 'http://localhost:5000'),
            'X-Title': os.environ.get('OPENROUTER_APP_NAME', 'AI Study Planner'),
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode('utf-8'))
    content = body.get('choices', [{}])[0].get('message', {}).get('content', '')
    print("API Key works successfully!")
    print(f"Response: {content}")
except Exception as e:
    print(f"API Key TEST FAILED: {str(e)}")
