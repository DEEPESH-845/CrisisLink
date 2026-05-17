"""Quick key verification — run from backend/ directory."""
from dotenv import load_dotenv
import os

load_dotenv()

gemini = os.environ.get("GEMINI_API_KEY", "")
maps = os.environ.get("GOOGLE_MAPS_API_KEY", "")
token = os.environ.get("CRISISLINK_API_TOKEN", "")
real_svc = os.environ.get("CRISISLINK_USE_REAL_SERVICES", "")
firebase_url = os.environ.get("FIREBASE_DATABASE_URL", "")

print(f"Gemini key:            {'✅ SET (' + gemini[:8] + '...)' if gemini else '❌ MISSING'}")
print(f"Maps key:              {'✅ SET (' + maps[:8] + '...)' if maps else '❌ MISSING'}")
print(f"API token:             {'✅ SET (' + token + ')' if token else '❌ MISSING'}")
print(f"Real services:         {'✅ ' + real_svc if real_svc else '⚠️  NOT SET (mocks will be used)'}")
print(f"Firebase DB URL:       {'✅ ' + firebase_url if firebase_url and 'your-project' not in firebase_url else '⚠️  PLACEHOLDER (Firebase writes will be skipped)'}")
