# CrisisLink — Emergency AI Co-Pilot

> **Real-time AI triage for India's 112 emergency network.**  
> Classifies Hindi/multilingual calls in under 3 seconds, dispatches the nearest unit, and guides callers with adaptive speech — all before a human operator says a word.

---

## What It Does

When a panicked caller dials 112, CrisisLink:

1. **Transcribes** the incoming audio stream in real time (Whisper / Google Speech-to-Text)
2. **Classifies** the emergency type, severity, and caller state using Gemini 2.5 Flash — in Hindi, Tamil, Telugu, Bengali, and more
3. **Dispatches** the best-matched response unit ranked by capability, ETA, and proximity via Google Maps Routes API
4. **Guides** the caller with adaptive Hindi/multilingual speech synthesised by Google Cloud TTS (calm reassurance for PANIC_HIGH, clinical steps for calm bystanders)
5. **Streams everything** to the operator dashboard in real time via Firebase RTDB

---

## Architecture

```
Telephony Bridge
      │  audio chunks (PCM 16-bit, 16 kHz, 500 ms)
      ▼
┌─────────────────────┐        ┌──────────────────────────┐
│  Speech Ingestion   │──────▶│   Intelligence Service   │
│  Service  :8001     │  text  │   (Gemini 2.5 Flash)     │
│  Whisper / GCP STT  │        │   :8002                  │
└─────────────────────┘        └──────────┬───────────────┘
                                          │ EmergencyClassification
                                          ▼
                               ┌──────────────────────────┐
                               │   Dispatch Service       │
                               │   (Google Maps Routes)   │
                               │   :8003                  │
                               └──────────┬───────────────┘
                                          │ DispatchCard
                                          ▼
                               ┌──────────────────────────┐
                               │   TTS Service            │
                               │   (Google Cloud TTS)     │
                               │   :8004                  │
                               └──────────────────────────┘
                                          │
                               ┌──────────▼───────────────┐
                               │  Firebase RTDB           │
                               │  (real-time message bus) │
                               └──────────▲───────────────┘
                                          │ streams
                               ┌──────────┴───────────────┐
                               │  Flutter Operator        │
                               │  Dashboard               │
                               └──────────────────────────┘
```

---

## Services

| Service | Port | Responsibility |
|---------|------|----------------|
| **Speech Ingestion** | 8001 | Receives audio chunks, accumulates rolling transcripts |
| **Intelligence** | 8002 | Gemini 2.5 Flash classification + adaptive guidance generation |
| **Dispatch** | 8003 | Maps ETA, capability scoring, unit ranking & dispatch confirmation |
| **TTS** | 8004 | Google Cloud TTS Neural2 voices for Hindi and 5 other Indian languages |

All services speak JSON over HTTP, require a Bearer token, and write to Firebase RTDB.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Flutter 3.x (for the dashboard)
- API keys: Gemini, Google Maps, Firebase service account

### 1. Clone

```bash
git clone https://github.com/DEEPESH-845/CrisisLink.git
cd CrisisLink
```

### 2. Configure environment

```bash
cp backend/.env.example backend/.env
# Fill in your keys:
```

| Variable | Where to get it |
|----------|----------------|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) |
| `GOOGLE_MAPS_API_KEY` | Google Cloud Console → APIs & Services → Routes API |
| `GOOGLE_APPLICATION_CREDENTIALS` | Firebase Console → Project Settings → Service Accounts → Generate Key |
| `FIREBASE_DATABASE_URL` | Firebase Console → Realtime Database → copy URL |
| `CRISISLINK_API_TOKEN` | Any secret string — used as the Bearer token |

> **Maps API note:** Enable **Routes API** in your Google Cloud project  
> (`console.cloud.google.com → APIs & Services → Routes API → Enable`),  
> then remove API key restrictions or add Routes API to the allowed list.

### 3. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Start all services

```bash
# From project root:
bash start.sh
```

This launches all 4 services with hot-reload and streams logs to the terminal.

### 5. Run the demo

```bash
# In a second terminal:
bash demo.sh
```

Expected output:

```
Step 1 — Gemini classifies Hindi transcript:
  emergency_type : MEDICAL
  severity       : CRITICAL
  panic_level    : PANIC_HIGH
  confidence     : 1.0
  model          : gemini-2.5-flash

Step 2 — Dispatch recommend (3 ranked units):
  [1] AMB_007  PGIMER Chandigarh    ETA: 4.0 min
  [2] AMB_012  GMC Sector 32        ETA: 4.0 min
  [3] AMB_019  GMSH Sector 16       ETA: 4.0 min

Step 3 — Dispatch confirmed: AMB_007 → dispatched

Step 4 — TTS synthesized Hindi CPR guidance
```

---

## API Reference

All endpoints require:  
`Authorization: Bearer <CRISISLINK_API_TOKEN>`

### Speech Ingestion `:8001`

#### `POST /api/v1/calls/{call_id}/audio-stream`
Ingest a raw audio chunk (PCM 16-bit, 16 kHz, ~500 ms).

```http
POST /api/v1/calls/call-001/audio-stream
Content-Type: application/octet-stream
Authorization: Bearer crisislink-dev-token
<binary audio data>
```

```json
{ "call_id": "call-001", "status": "accepted", "chunks_processed": 1 }
```

#### `GET /api/v1/calls/{call_id}/transcript`
Get the accumulated transcript for a call.

```json
{ "call_id": "call-001", "transcript": "mere papa gir gaye...", "language_detected": "hi", "chunks_processed": 4 }
```

---

### Intelligence `:8002`

#### `POST /api/v1/calls/{call_id}/classify`

```json
// Request
{ "transcript": "mere papa gir gaye unhe saans nahi aa rahi jaldi aao" }
```

```json
// Response
{
  "classification": {
    "call_id": "call-001",
    "emergency_type": "MEDICAL",
    "severity": "CRITICAL",
    "caller_state": { "panic_level": "PANIC_HIGH", "caller_role": "BYSTANDER" },
    "language_detected": "hi",
    "key_facts": ["father fell down", "not breathing"],
    "confidence": 1.0,
    "model_version": "gemini-2.5-flash"
  }
}
```

**Emergency types:** `MEDICAL` · `FIRE` · `ACCIDENT` · `CRIME` · `NATURAL_DISASTER` · `UNKNOWN`  
**Severity:** `CRITICAL` · `HIGH` · `MODERATE` · `LOW`  
**Panic level:** `PANIC_HIGH` · `PANIC_MODERATE` · `CALM`

#### `POST /api/v1/calls/{call_id}/guidance`

```json
// Request
{
  "classification": { "emergency_type": "MEDICAL", "severity": "CRITICAL", ... },
  "caller_state": { "panic_level": "PANIC_HIGH", "caller_role": "BYSTANDER" }
}
```

```json
// Response
{ "call_id": "call-001", "guidance": "Ghabrao mat, main aapke saath hoon..." }
```

---

### Dispatch `:8003`

#### `POST /api/v1/calls/{call_id}/dispatch/recommend`

```json
// Request
{
  "classification": { "emergency_type": "MEDICAL", "severity": "CRITICAL", ... },
  "caller_location": { "lat": 30.7333, "lng": 76.7794 }
}
```

```json
// Response
{
  "recommendations": [
    {
      "unit_id": "AMB_007",
      "unit_type": "ambulance",
      "hospital_or_station": "PGIMER Chandigarh",
      "eta_minutes": 4.0,
      "capability_match": 0.9,
      "composite_score": 0.87
    }
  ]
}
```

#### `POST /api/v1/calls/{call_id}/dispatch/confirm`

```json
// Request
{
  "unit_id": "AMB_007",
  "emergency_type": "MEDICAL",
  "severity": "CRITICAL",
  "caller_lat": 30.7333,
  "caller_lng": 76.7794,
  "key_facts": ["not breathing"]
}
```

```json
// Response
{ "unit_id": "AMB_007", "status": "dispatched" }
```

---

### TTS `:8004`

#### `POST /api/v1/tts/synthesize`

```json
// Request
{
  "text": "Ghabrao mat, main aapke saath hoon. Unhe seedha letao kisi sakht jagah par.",
  "language": "hi",
  "voice_config": { "name": "hi-IN-Neural2-A", "speaking_rate": 0.82 }
}
```

Returns `audio/mpeg` binary on success, or a `503` JSON fallback when credentials are unavailable:

```json
{ "status": "fallback", "reason": "...", "text": "<original guidance text>", "language": "hi" }
```

**Supported languages:** `hi` · `ta` · `te` · `bn` · `mr` · `en`

---

## Fallback & Resilience

| Component | What happens without it |
|-----------|------------------------|
| Firebase (no service account) | Classification/dispatch results logged locally; dashboard shows no live updates |
| Google Maps (key restriction) | Urban straight-line ETA used (25 km/h, 1.5× tortuosity, 4 min minimum) |
| Google Cloud TTS (no credentials) | HTTP 503 with original text — operator relays manually |
| Gemini quota exhausted | Exponential backoff (30s × 2ⁿ), up to 2 retries, then UNKNOWN classification |

---

## Project Structure

```
CrisisLink/
├── backend/
│   ├── speech_ingestion/   # Audio ingestion + Whisper transcription
│   ├── intelligence/       # Gemini classifier + guidance generator
│   ├── dispatch/           # Maps ETA, unit ranking, FCM notifications
│   ├── tts/                # Google Cloud TTS Neural2
│   ├── shared/             # Pydantic models, Firebase paths, enums
│   ├── integration/        # End-to-end pipeline wiring
│   ├── tests/              # Unit + property-based tests (Hypothesis)
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── .env.example        # Template — copy to .env and fill in keys
│   └── seed_firebase.py    # Seed 5 Chandigarh demo units into Firebase
├── frontend/               # Flutter operator dashboard
│   └── lib/
│       ├── main.dart
│       ├── models/
│       ├── services/
│       └── widgets/
├── shared/
│   └── firebase/           # Firebase schema docs
├── start.sh                # Launch all 4 services
├── demo.sh                 # End-to-end demo flow
└── README_DEMO.md          # Step-by-step demo guide
```

---

## Testing

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

The test suite includes:
- **Unit tests** for every service module
- **Property-based tests** (Hypothesis) for schema validation, RBAC, geospatial filtering, confidence thresholds, guidance register selection, and more
- **Integration tests** for the full classification → dispatch pipeline

---

## Firebase Schema

```
/calls/{call_id}/
  transcript          string     rolling speech text
  classification/     object     EmergencyClassification
  caller_state/       object     { panic_level, caller_role }
  guidance/           object     { status, text, language, protocol_type }

/units/{unit_id}/
  type                string     ambulance | fire_brigade | police
  status              string     available | dispatched | offline
  location/           object     { lat, lng }
  hospital_or_station string
  capabilities        array
```

---

## Seeding Demo Data

To populate Firebase with 5 Chandigarh response units:

```bash
cd backend
python seed_firebase.py
```

Units seeded: AMB_007 (PGIMER), AMB_012 (GMC Sector 32), AMB_019 (GMSH Sector 16), FIRE_003 (Sector 17), POL_021 (Sector 11).

---

## Roadmap

- [ ] Live Whisper integration (currently in-memory accumulator)
- [ ] WebSocket streaming for partial Gemini classifications
- [ ] BigQuery audit log pipeline
- [ ] Multi-language TTS with automatic language detection
- [ ] iOS/Android responder app
- [ ] Load balancing across multiple intelligence workers

---

## License

Proprietary — CrisisLink. All rights reserved.
