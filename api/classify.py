"""Vercel serverless function — POST /api/classify.

Proxies classification requests to Gemini 2.5 Flash.
Falls back to deterministic mock data when GEMINI_API_KEY is unset.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import time


MOCK_RESPONSE = {
    "classification": {
        "call_id": "vercel-demo",
        "emergency_type": "MEDICAL",
        "severity": "CRITICAL",
        "caller_state": {"panic_level": "PANIC_HIGH", "caller_role": "BYSTANDER"},
        "language_detected": "hi",
        "key_facts": ["father fell down", "not breathing", "unresponsive"],
        "confidence": 0.97,
        "model_version": "gemini-2.5-flash (mock)",
        "timestamp": "2026-05-17T10:00:00Z",
    }
}


class handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        transcript = body.get("transcript", "")
        call_id = body.get("call_id", "vercel-demo")

        api_key = os.environ.get("GEMINI_API_KEY", "")
        result = None

        if api_key:
            try:
                result = self._gemini_classify(api_key, transcript, call_id)
            except Exception as exc:
                result = None

        if result is None:
            resp = dict(MOCK_RESPONSE)
            resp["classification"] = dict(resp["classification"])
            resp["classification"]["call_id"] = call_id
            result = resp

        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def _gemini_classify(self, api_key: str, transcript: str, call_id: str) -> dict:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt = (
            f"Classify this emergency call transcript: '{transcript}'\n\n"
            "Respond with ONLY a JSON object with these fields:\n"
            "emergency_type (MEDICAL|FIRE|ACCIDENT|CRIME|NATURAL_DISASTER|UNKNOWN),\n"
            "severity (CRITICAL|HIGH|MODERATE|LOW),\n"
            "caller_state: {panic_level: PANIC_HIGH|PANIC_MODERATE|CALM, caller_role: VICTIM|BYSTANDER|WITNESS},\n"
            "language_detected (ISO 639-1 code),\n"
            "key_facts (array of short strings),\n"
            "confidence (0.0-1.0)"
        )
        started = time.monotonic()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=256,
                response_mime_type="application/json",
            ),
        )
        raw = json.loads(response.text)
        return {
            "classification": {
                "call_id": call_id,
                "emergency_type": raw.get("emergency_type", "UNKNOWN"),
                "severity": raw.get("severity", "MODERATE"),
                "caller_state": raw.get("caller_state", {"panic_level": "CALM", "caller_role": "BYSTANDER"}),
                "language_detected": raw.get("language_detected", "hi"),
                "key_facts": raw.get("key_facts", []),
                "confidence": float(raw.get("confidence", 0.5)),
                "model_version": "gemini-2.5-flash",
                "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            }
        }

    def log_message(self, *args):
        pass
