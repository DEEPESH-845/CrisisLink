# CrisisLink Backend Services

Backend services for the **CrisisLink Emergency AI Co-Pilot**, built with Python and FastAPI. The backend is organized as four independent microservices plus shared libraries, all orchestrated through an integration pipeline with Firebase Realtime Database as the message bus.

---

## Architecture

```
Caller Audio → [Speech Ingestion] → Firebase RTDB transcript
                                        ↓
                                  [Intelligence Engine]
                                   ↓              ↓
                            [Dispatch Engine]  [Guidance + TTS]
                                   ↓              ↓
                            Operator Dashboard   Caller Audio
```

## Services

| Service | Port | Description |
|---|---|---|
| **speech_ingestion/** | 8001 | Audio chunking, Whisper transcription, STT failover |
| **intelligence/** | 8002 | Gemini-powered emergency classification, caller state detection, guidance generation |
| **dispatch/** | 8003 | Unit filtering, traffic-aware ETA calculation, composite scoring, dispatch confirmation |
| **tts/** | 8004 | Google Cloud TTS Neural2 voice synthesis for caller guidance |

### Shared Modules

| Module | Description |
|---|---|
| **shared/** | Pydantic data models, Firebase RTDB path helpers, common utilities |
| **integration/** | End-to-end pipeline orchestrator, service wiring, security & compliance config |

---

## Prerequisites

- **Python 3.11+** — required by `pyproject.toml`
- **pip** — comes with Python
- **Google Cloud credentials** — for Firebase Admin SDK, Google Maps, Gemini, and Cloud TTS
- **Firebase project** — with Realtime Database enabled

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/<your-org>/crisislink.git
cd crisislink/backend
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

Install the project in editable mode with dev dependencies:

```bash
pip install -e ".[dev]"
```

Or install from the requirements file:

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

Create a `.env` file in the `backend/` directory (this file is gitignored):

```bash
# Firebase
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/firebase-service-account.json
FIREBASE_DATABASE_URL=https://<your-project>-default-rtdb.firebaseio.com

# Google Maps (Dispatch Service)
GOOGLE_MAPS_API_KEY=your_maps_api_key

# Gemini (Intelligence Service)
GEMINI_API_KEY=your_gemini_api_key

# Google Cloud TTS (TTS Service)
GOOGLE_CLOUD_TTS_ENABLED=true

# Auth (for local development — services expect Bearer tokens)
AUTH_SECRET=your_local_dev_secret
```

### 5. Set up Firebase service account

1. Go to [Firebase Console](https://console.firebase.google.com/) → Project Settings → Service Accounts
2. Click **Generate new private key**
3. Save the JSON file and point `GOOGLE_APPLICATION_CREDENTIALS` to it

---

## Running Services

Each service is a standalone FastAPI app. Run them individually with Uvicorn:

```bash
# Speech Ingestion Service
uvicorn speech_ingestion.app:app --host 0.0.0.0 --port 8001 --reload

# Intelligence Service
uvicorn intelligence.app:app --host 0.0.0.0 --port 8002 --reload

# Dispatch Service
uvicorn dispatch.app:app --host 0.0.0.0 --port 8003 --reload

# TTS Service
uvicorn tts.app:app --host 0.0.0.0 --port 8004 --reload
```

Each service exposes interactive API docs at `http://localhost:<port>/docs`.

---

## API Endpoints

### Speech Ingestion (`/api/v1/calls/{call_id}/...`)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/audio-stream` | Ingest a raw PCM audio chunk (500ms, 16-bit, 16kHz) |
| GET | `/transcript` | Retrieve the current transcript for a call |

### Intelligence (`/api/v1/calls/{call_id}/...`)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/classify` | Classify an emergency from a transcript |
| POST | `/guidance` | Generate caller guidance from classification |

### Dispatch (`/api/v1/calls/{call_id}/dispatch/...`)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/recommend` | Generate ranked dispatch recommendations |
| POST | `/confirm` | Confirm dispatch of a unit |

### TTS (`/api/v1/tts/...`)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/synthesize` | Synthesize guidance text into speech (returns MP3) |

All endpoints require a valid **Bearer token** in the `Authorization` header.

---

## Testing

The project uses **pytest** with **Hypothesis** for property-based testing.

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_dispatch.py

# Run tests matching a pattern
pytest -k "test_classification"
```

Test files are located in `tests/` and also co-located within service directories. The test configuration is defined in `pyproject.toml` under `[tool.pytest.ini_options]`.

---

## Project Structure

```
backend/
├── dispatch/                # Dispatch Service
│   ├── app.py               # FastAPI app & endpoints
│   ├── auth.py              # Bearer token verification
│   ├── confirmation.py      # Dispatch confirmation, FCM, audit
│   ├── geospatial.py        # Geo utilities (radius filtering)
│   ├── maps_client.py       # Google Maps Routes API client
│   ├── ranking.py           # Composite scoring algorithm
│   ├── schemas.py           # Pydantic request/response models
│   ├── service.py           # Core recommendation logic
│   └── unit_store.py        # Unit availability store (Firebase)
├── intelligence/            # Intelligence Service
│   ├── app.py               # FastAPI app & endpoints
│   ├── auth.py              # Bearer token verification
│   ├── confidence_flagging.py  # Low-confidence alert logic
│   ├── gemini_classifier.py # Gemini API integration
│   ├── gemini_prompts.py    # Prompt templates
│   ├── guidance_generator.py # Caller guidance generation
│   ├── schemas.py           # Pydantic request/response models
│   ├── service.py           # Classification & guidance orchestration
│   └── timeout_monitor.py   # Gemini response timeout handling
├── speech_ingestion/        # Speech Ingestion Service
│   ├── app.py               # FastAPI app & endpoints
│   ├── audit_logger.py      # BigQuery audit logging
│   ├── auth.py              # Bearer token verification
│   ├── chunker.py           # Audio chunk management
│   ├── failover_transcriber.py  # Whisper → Google STT failover
│   ├── firebase_writer.py   # Firebase RTDB transcript writer
│   ├── latency_monitor.py   # Transcription latency tracking
│   ├── schemas.py           # Pydantic request/response models
│   ├── service.py           # Ingestion orchestration
│   └── transcriber.py       # Whisper transcription client
├── tts/                     # TTS Service
│   ├── app.py               # FastAPI app & endpoints
│   ├── auth.py              # Bearer token verification
│   ├── schemas.py           # Pydantic request/response models
│   ├── service.py           # Synthesis orchestration
│   └── tts_client.py        # Google Cloud TTS client
├── shared/                  # Shared libraries
│   ├── firebase/
│   │   └── paths.py         # Firebase RTDB path constants
│   └── models/              # Pydantic data models
│       ├── audit.py         # Audit event types
│       ├── call_session.py  # Call session model
│       ├── classification.py # EmergencyClassification model
│       ├── dispatch.py      # DispatchCard, Recommendation models
│       ├── enums.py         # Severity, EmergencyType, etc.
│       └── response_unit.py # ResponseUnit model
├── integration/             # Integration & orchestration
│   ├── pipeline.py          # End-to-end call pipeline
│   ├── operator_wiring.py   # Operator service wiring
│   ├── responder_wiring.py  # Responder service wiring
│   ├── security.py          # Encryption, RBAC, data retention
│   └── subsystem_error_notification.py
├── tests/                   # Test suite
├── pyproject.toml           # Project config & dependencies
├── requirements.txt         # Flat dependency list
└── README.md
```

---

## Key Dependencies

| Package | Purpose |
|---|---|
| `fastapi` | Web framework for all service APIs |
| `uvicorn` | ASGI server |
| `pydantic` | Data validation and serialization |
| `firebase-admin` | Firebase Realtime Database & Auth |
| `google-cloud-bigquery` | Audit log storage |
| `hypothesis` | Property-based testing |
| `pytest` | Test runner |
| `httpx` | Async HTTP client for testing |

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError` for shared/service modules | Make sure you installed with `pip install -e ".[dev]"` (editable mode) |
| Firebase credential errors | Verify `GOOGLE_APPLICATION_CREDENTIALS` points to a valid service account JSON |
| Tests fail with import errors | Ensure you're running `pytest` from the `backend/` directory with the venv activated |
| Port already in use | Change the `--port` flag or kill the process using that port |
