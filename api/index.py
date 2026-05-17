"""CrisisLink — Vercel serverless backend.

Single FastAPI application exposing all four service endpoints so the
entire stack deploys as one Vercel function:

  GET  /api/health
  POST /api/v1/calls/{call_id}/classify          (Gemini 2.5 Flash)
  POST /api/v1/calls/{call_id}/guidance
  POST /api/v1/calls/{call_id}/dispatch/recommend
  POST /api/v1/calls/{call_id}/dispatch/confirm
  POST /api/v1/tts/synthesize
  POST /api/v1/calls/{call_id}/audio-stream
  GET  /api/v1/calls/{call_id}/transcript

Environment variables (set in Vercel dashboard):
  GEMINI_API_KEY            — required for real AI classification
  CRISISLINK_API_TOKEN      — Bearer token (default: crisislink-dev-token)
  FIREBASE_SERVICE_ACCOUNT_B64 — base64-encoded service account JSON (optional)
  FIREBASE_DATABASE_URL     — Firebase RTDB URL (optional)
"""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

app = FastAPI(title="CrisisLink API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Auth ──────────────────────────────────────────────────────────────────────
_TOKEN = os.environ.get("CRISISLINK_API_TOKEN", "crisislink-dev-token")


def _auth(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Bearer token")
    if authorization.split(" ", 1)[1] != _TOKEN:
        raise HTTPException(403, "Invalid token")


# ── Mock / fallback classification ────────────────────────────────────────────
_MOCK_RAW: dict[str, Any] = {
    "emergency_type": "MEDICAL",
    "severity": "CRITICAL",
    "caller_state": {"panic_level": "PANIC_HIGH", "caller_role": "BYSTANDER"},
    "language_detected": "hi",
    "key_facts": ["father fell down", "not breathing", "unresponsive"],
    "confidence": 0.97,
    "model_version": "mock-fallback",
}


def _gemini_classify(transcript: str) -> dict[str, Any]:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return _MOCK_RAW
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                f"You are an emergency dispatch AI for India's 112 system.\n"
                f"Transcript: \"{transcript}\"\n\n"
                "Return ONLY valid JSON with exactly these fields:\n"
                "{\n"
                '  "emergency_type": "MEDICAL|FIRE|ACCIDENT|CRIME|NATURAL_DISASTER|UNKNOWN",\n'
                '  "severity": "CRITICAL|HIGH|MODERATE|LOW",\n'
                '  "caller_state": {"panic_level": "PANIC_HIGH|PANIC_MODERATE|CALM", "caller_role": "VICTIM|BYSTANDER|WITNESS"},\n'
                '  "language_detected": "hi|en|ta|te|bn|mr",\n'
                '  "key_facts": ["fact1", "fact2"],\n'
                '  "confidence": 0.0\n'
                "}"
            ),
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=300,
                response_mime_type="application/json",
            ),
        )
        raw = json.loads(response.text)
        raw.setdefault("model_version", "gemini-2.5-flash")
        return raw
    except Exception:
        return _MOCK_RAW


# ── Geospatial + ETA ──────────────────────────────────────────────────────────
def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _urban_eta(dist_km: float) -> float:
    """Realistic urban ETA: 25 km/h, 1.5x tortuosity, 4 min minimum."""
    return max(dist_km * 1.5 / 25.0 * 60.0, 4.0)


_maps_key_blocked: bool = False


def _routes_eta(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> float | None:
    """Call Google Maps Routes API; return minutes or None to trigger fallback."""
    global _maps_key_blocked
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key or _maps_key_blocked:
        return None
    payload = json.dumps({
        "origin":      {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lng}}},
        "destination": {"location": {"latLng": {"latitude": dest_lat,   "longitude": dest_lng}}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "computeAlternativeRoutes": False,
        "languageCode": "en-IN",
        "units": "METRIC",
    }).encode()
    req = urllib.request.Request(
        "https://routes.googleapis.com/directions/v2:computeRoutes",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        routes = data.get("routes") or []
        if not routes:
            return None
        duration = routes[0].get("duration", "")
        if not isinstance(duration, str) or not duration.endswith("s"):
            return None
        return float(duration[:-1]) / 60.0
    except urllib.error.HTTPError as e:
        if e.code == 403:
            _maps_key_blocked = True  # stop retrying for this function instance
        return None
    except Exception:
        return None


# ── Demo response units — Chandigarh ──────────────────────────────────────────
_UNITS = [
    {"unit_id": "AMB_007",  "type": "ambulance",    "lat": 30.7340, "lng": 76.7820, "station": "PGIMER Chandigarh",        "caps": {"CARDIAC", "TRAUMA"}},
    {"unit_id": "AMB_012",  "type": "ambulance",    "lat": 30.7290, "lng": 76.7750, "station": "GMC Sector 32",             "caps": {"GENERAL"}},
    {"unit_id": "AMB_019",  "type": "ambulance",    "lat": 30.7380, "lng": 76.7700, "station": "GMSH Sector 16",            "caps": {"PEDIATRIC", "TRAUMA"}},
    {"unit_id": "FIRE_003", "type": "fire_brigade", "lat": 30.7400, "lng": 76.7900, "station": "Fire Station Sector 17",   "caps": {"FIRE_RESCUE"}},
    {"unit_id": "POL_021",  "type": "police",       "lat": 30.7310, "lng": 76.7800, "station": "Police Station Sector 11", "caps": {"GENERAL"}},
]

_NEEDED: dict[str, set[str]] = {
    "MEDICAL":          {"CARDIAC", "TRAUMA", "GENERAL", "PEDIATRIC"},
    "FIRE":             {"FIRE_RESCUE", "GENERAL"},
    "ACCIDENT":         {"TRAUMA", "GENERAL"},
    "CRIME":            {"GENERAL"},
    "NATURAL_DISASTER": {"TRAUMA", "GENERAL", "FIRE_RESCUE"},
    "UNKNOWN":          {"GENERAL"},
}

# ── Firebase (optional) ───────────────────────────────────────────────────────
_fb_initialized = False


def _firebase_set(path: str, data: Any) -> None:
    global _fb_initialized
    sa_b64 = os.environ.get("FIREBASE_SERVICE_ACCOUNT_B64", "")
    db_url = os.environ.get("FIREBASE_DATABASE_URL", "")
    if not sa_b64 or not db_url:
        return
    try:
        import base64
        import firebase_admin  # type: ignore
        from firebase_admin import credentials, db  # type: ignore

        if not _fb_initialized:
            sa = json.loads(base64.b64decode(sa_b64))
            firebase_admin.initialize_app(
                credentials.Certificate(sa),
                {"databaseURL": db_url},
            )
            _fb_initialized = True
        db.reference(path).set(data)
    except Exception:
        pass


# ── Guidance text ─────────────────────────────────────────────────────────────
_GUIDANCE: dict[tuple[str, str], str] = {
    ("MEDICAL", "PANIC_HIGH"):    "Ghabrao mat — main aapke saath hoon. Unhe seedha letao kisi sakht jagah par. Unki naak ke paas haath rakhein aur dekhein kya saans aa rahi hai.",
    ("MEDICAL", "PANIC_MODERATE"):"Rogi ko seedha sulaayein. Unki naadi check karein. Ambulance aa rahi hai — seedha rakhein.",
    ("MEDICAL", "CALM"):          "30 baar chhati dabaayein phir 2 saans dein. Yahi karte rahein jab tak ambulance na aaye.",
    ("FIRE",    "PANIC_HIGH"):    "Sirf ek kaam karo — abhi bahar niklo. Neeche jhukkar crawl karo. Darwaza band karo peeche se.",
    ("FIRE",    "CALM"):          "Sabko neeche seedhiyon se bahar nikalein. Lift bilkul mat lo. Darwaze band karo.",
    ("ACCIDENT","PANIC_HIGH"):    "Koi bhi injured vyakti ko hilao mat. Ambulance raste mein hai. Unhe garam rakhein.",
    ("CRIME",   "PANIC_HIGH"):    "Surakshit jagah par jao. Darwaza band karo. Police aa rahi hai — phone mat rakho.",
}


def _get_guidance(emergency_type: str, panic_level: str) -> str:
    return (
        _GUIDANCE.get((emergency_type, panic_level))
        or _GUIDANCE.get((emergency_type, "CALM"))
        or "Madad aa rahi hai. Shant rahein aur phone par bane rahein."
    )


# ── In-memory transcript store (per function instance) ───────────────────────
_transcripts: dict[str, str] = {}


# ═════════════════════════════════════════════════════════════════════════════
# API Routes
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "gemini": bool(os.environ.get("GEMINI_API_KEY")),
        "maps": bool(os.environ.get("GOOGLE_MAPS_API_KEY")) and not _maps_key_blocked,
        "firebase": bool(os.environ.get("FIREBASE_SERVICE_ACCOUNT_B64") and os.environ.get("FIREBASE_DATABASE_URL")),
    }


# ── Speech Ingestion ──────────────────────────────────────────────────────────

class AudioAccepted(BaseModel):
    call_id: str
    status: str
    chunks_processed: int


@app.post("/api/v1/calls/{call_id}/audio-stream", response_model=AudioAccepted)
async def audio_stream(
    call_id: str,
    authorization: str | None = Header(default=None),
) -> AudioAccepted:
    _auth(authorization)
    _transcripts[call_id] = _transcripts.get(call_id, "")
    count = _transcripts.get(f"{call_id}__count", 0) + 1
    _transcripts[f"{call_id}__count"] = count
    return AudioAccepted(call_id=call_id, status="accepted", chunks_processed=count)


@app.get("/api/v1/calls/{call_id}/transcript")
async def get_transcript(
    call_id: str,
    authorization: str | None = Header(default=None),
):
    _auth(authorization)
    t = _transcripts.get(call_id)
    if t is None:
        raise HTTPException(404, f"No transcript found for call '{call_id}'")
    return {
        "call_id": call_id,
        "transcript": t,
        "language_detected": "hi",
        "chunks_processed": _transcripts.get(f"{call_id}__count", 0),
    }


# ── Intelligence — Classification ─────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    transcript: str


@app.post("/api/v1/calls/{call_id}/classify")
async def classify(
    call_id: str,
    body: ClassifyRequest,
    authorization: str | None = Header(default=None),
):
    _auth(authorization)
    raw = _gemini_classify(body.transcript)

    classification = {
        "call_id": call_id,
        "emergency_type": raw.get("emergency_type", "UNKNOWN"),
        "severity": raw.get("severity", "MODERATE"),
        "caller_state": raw.get("caller_state", {"panic_level": "CALM", "caller_role": "BYSTANDER"}),
        "language_detected": raw.get("language_detected", "hi"),
        "key_facts": raw.get("key_facts", []),
        "confidence": float(raw.get("confidence", 0.5)),
        "model_version": raw.get("model_version", "gemini-2.5-flash"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    _firebase_set(f"/calls/{call_id}/classification", classification)
    return {"classification": classification}


# ── Intelligence — Guidance ───────────────────────────────────────────────────

class CallerStateIn(BaseModel):
    panic_level: str = "CALM"
    caller_role: str = "BYSTANDER"


class ClassificationIn(BaseModel):
    call_id: str
    emergency_type: str = "UNKNOWN"
    severity: str = "MODERATE"
    caller_state: CallerStateIn = CallerStateIn()
    language_detected: str = "hi"
    key_facts: list[str] = []
    confidence: float = 0.5
    timestamp: str = ""
    model_version: str = ""


class GuidanceRequest(BaseModel):
    classification: ClassificationIn
    caller_state: CallerStateIn


@app.post("/api/v1/calls/{call_id}/guidance")
async def guidance(
    call_id: str,
    body: GuidanceRequest,
    authorization: str | None = Header(default=None),
):
    _auth(authorization)
    severity = body.classification.severity
    if severity not in ("CRITICAL", "HIGH"):
        return {"call_id": call_id, "guidance": ""}

    text = _get_guidance(
        body.classification.emergency_type,
        body.caller_state.panic_level,
    )
    _firebase_set(f"/calls/{call_id}/guidance", {"status": "active", "text": text, "language": "hi"})
    return {"call_id": call_id, "guidance": text}


# ── Dispatch — Recommend ──────────────────────────────────────────────────────

class LocationIn(BaseModel):
    lat: float
    lng: float


class RecommendRequest(BaseModel):
    classification: ClassificationIn
    caller_location: LocationIn


@app.post("/api/v1/calls/{call_id}/dispatch/recommend")
async def recommend(
    call_id: str,
    body: RecommendRequest,
    authorization: str | None = Header(default=None),
):
    _auth(authorization)
    needed = _NEEDED.get(body.classification.emergency_type, {"GENERAL"})
    clat, clng = body.caller_location.lat, body.caller_location.lng

    scored = []
    for u in _UNITS:
        dist = _haversine(u["lat"], u["lng"], clat, clng)
        real_eta = _routes_eta(u["lat"], u["lng"], clat, clng)
        eta = real_eta if real_eta is not None else _urban_eta(dist)
        cap_ok = bool(u["caps"] & needed)
        score = (1.0 / (1 + eta / 10)) * 0.7 + (0.3 if cap_ok else 0.05)
        scored.append({
            "unit_id": u["unit_id"],
            "unit_type": u["type"],
            "hospital_or_station": u["station"],
            "eta_minutes": round(eta, 1),
            "eta_source": "maps" if real_eta is not None else "estimated",
            "capability_match": 1.0 if cap_ok else 0.3,
            "composite_score": round(score, 3),
            "distance_km": round(dist, 2),
        })

    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    top3 = scored[:3]
    _firebase_set(f"/calls/{call_id}/dispatch", {"status": "pending", "recommendations": top3})
    return {"recommendations": top3, "call_id": call_id}


# ── Dispatch — Confirm ────────────────────────────────────────────────────────

class ConfirmRequest(BaseModel):
    unit_id: str
    emergency_type: str = "MEDICAL"
    severity: str = "CRITICAL"
    caller_lat: float = 0.0
    caller_lng: float = 0.0
    key_facts: list[str] = []


@app.post("/api/v1/calls/{call_id}/dispatch/confirm")
async def confirm(
    call_id: str,
    body: ConfirmRequest,
    authorization: str | None = Header(default=None),
):
    _auth(authorization)
    _firebase_set(f"/units/{body.unit_id}", {"status": "dispatched"})
    _firebase_set(f"/calls/{call_id}/dispatch/confirmed_unit", body.unit_id)
    return {"unit_id": body.unit_id, "status": "dispatched", "call_id": call_id}


# ── TTS — Synthesize ──────────────────────────────────────────────────────────

class VoiceConfig(BaseModel):
    name: str = "hi-IN-Neural2-A"
    speaking_rate: float = 1.0


class TTSRequest(BaseModel):
    text: str
    language: str = "hi"
    voice_config: VoiceConfig = VoiceConfig()


@app.post("/api/v1/tts/synthesize")
async def synthesize(
    body: TTSRequest,
    authorization: str | None = Header(default=None),
):
    _auth(authorization)

    sa_b64 = os.environ.get("FIREBASE_SERVICE_ACCOUNT_B64", "")
    if sa_b64:
        try:
            import base64
            import json as _j
            import tempfile

            from google.cloud import texttospeech  # type: ignore

            sa = _j.loads(base64.b64decode(sa_b64))
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                _j.dump(sa, f)
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = f.name

            client = texttospeech.TextToSpeechClient()
            resp = client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=body.text),
                voice=texttospeech.VoiceSelectionParams(
                    language_code=f"{body.language}-IN",
                    name=body.voice_config.name,
                ),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3,
                    speaking_rate=body.voice_config.speaking_rate,
                ),
            )
            return Response(content=resp.audio_content, media_type="audio/mpeg")
        except Exception:
            pass

    return JSONResponse({
        "status": "fallback",
        "text": body.text,
        "language": body.language,
        "reason": "Google Cloud TTS not configured — displaying text guidance.",
    })
