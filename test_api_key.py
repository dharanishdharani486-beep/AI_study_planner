import os
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)
api_key = os.environ.get('GEMINI_API_KEY')

print(f"Testing API key starting with: {api_key[:10]}..." if api_key else "No API key found")

try:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents='Hello'
    )
    print("API Key works successfully!")
except Exception as e:
    print(f"API Key TEST FAILED: {str(e)}")
