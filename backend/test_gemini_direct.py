"""Direct Gemini API test — run after rate-limit cooldown."""
import os, sys, time
from dotenv import load_dotenv
load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY", "")
if not api_key:
    print("ERROR: GEMINI_API_KEY not set")
    sys.exit(1)

print(f"API key: {api_key[:8]}...")
print("Calling gemini-2.0-flash...")

from google import genai
from google.genai import types

client = genai.Client(api_key=api_key)
t0 = time.monotonic()
try:
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=(
            'Classify this emergency: "mere papa gir gaye unhe saans nahi aa rahi". '
            'Respond ONLY with this JSON (no other text): '
            '{"emergency_type":"MEDICAL","severity":"CRITICAL","confidence":0.91}'
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    elapsed = time.monotonic() - t0
    print(f"SUCCESS ({elapsed:.1f}s): {response.text}")
except Exception as e:
    elapsed = time.monotonic() - t0
    print(f"FAILED ({elapsed:.1f}s): {type(e).__name__}: {str(e)[:500]}")
