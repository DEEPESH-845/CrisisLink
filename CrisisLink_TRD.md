# CrisisLink — Technical Requirements Document (TRD)
**Version:** 1.0
**Date:** April 2026
**Author:** Prabinder Singh, Thapar Institute of Engineering & Technology
**Hackathon:** Solution Challenge 2026 — Google Developers × Hack2Skill

---

## 1. System Architecture Overview

CrisisLink is structured as a **six-layer real-time AI orchestration system.** All layers execute concurrently from the moment a call connects. No layer waits for the previous layer to complete before starting work.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CRISISLINK SYSTEM                           │
│                                                                     │
│  [L1] Audio Ingestion & Streaming Pipeline                         │
│          ↓ (chunked audio, 500ms)                                   │
│  [L2] Speech Recognition Layer (Whisper Large-v3)                  │
│          ↓ (rolling transcript, streamed)                           │
│  [L3] AI Intelligence Layer (Gemini 1.5 Pro)                       │
│          ↓ (structured JSON: type, severity, facts)                 │
│  [L4] Dispatch Orchestration Layer (Firebase + Maps)               │
│          ↓ (ranked unit list, ETA)                                  │
│  [L5] Caller Guidance Layer (Gemini + Cloud TTS)                   │
│          ↓ (language-native audio guidance)                         │
│  [L6] Presentation Layer (Flutter Web + Mobile)                    │
│                                                                     │
│  Cross-cutting: Firebase Realtime DB (state bus for all layers)    │
│  Cross-cutting: Cloud Run (compute for L2, L3, L5 backends)        │
│  Cross-cutting: BigQuery + Vertex AI (async analytics)             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Layer 1 — Audio Ingestion & Streaming Pipeline

### 2.1 Purpose
Capture caller audio from the telephony bridge, chunk it into processable segments, and stream it to the speech recognition layer with minimal buffering latency.

### 2.2 Audio Input Sources

**Demo / Hackathon:**
- Browser microphone via WebRTC (MediaRecorder API)
- Pre-recorded `.wav` clips played through browser for demo reliability

**Production path:**
- SIP trunk bridge via Exotel (India-based telephony, supports 112 integration)
- WebSocket audio stream → Cloud Run ingestion endpoint

### 2.3 Audio Chunking Strategy

```python
CHUNK_SIZE_MS = 500          # 500ms audio chunks
SAMPLE_RATE = 16000          # 16kHz mono — Whisper optimal
BIT_DEPTH = 16               # PCM 16-bit
FORMAT = "wav"               # Whisper native input format
OVERLAP_MS = 100             # 100ms overlap between chunks for boundary safety
```

**Why 500ms chunks:** Whisper processes audio in segments. 500ms gives < 1.5s end-to-end latency per chunk while maintaining enough context for accurate transcription. Smaller chunks increase API overhead; larger chunks increase perceived latency.

### 2.4 Streaming Architecture

```
Browser/SIP audio stream
        ↓
WebSocket connection → Cloud Run Ingestion Service (Python FastAPI)
        ↓
AudioChunkBuffer: accumulates 500ms, emits with 100ms overlap
        ↓
Chunk pushed to Pub/Sub topic: crisislink-audio-chunks
        ↓
Whisper Worker (Cloud Run) subscribes and processes
        ↓
Transcript segment pushed to Firebase: /calls/{call_id}/transcript_segments[]
```

Google Cloud Pub/Sub is used between ingestion and Whisper to decouple the audio capture rate from the Whisper processing rate, allowing backpressure handling during GPU warm-up.

### 2.5 Technical Specs

| Parameter | Value |
|---|---|
| Protocol | WebSocket (wss://) |
| Audio format | PCM WAV, 16kHz, mono, 16-bit |
| Chunk interval | 500ms with 100ms overlap |
| Pub/Sub topic | crisislink-audio-chunks |
| Max call duration handled | 30 minutes |
| Concurrent calls (demo) | 1 |
| Concurrent calls (production target) | 500 per region |

---

## 3. Layer 2 — Speech Recognition Layer

### 3.1 Model Selection: OpenAI Whisper Large-v3

**Model:** `openai/whisper-large-v3`
**Deployment:** Self-hosted on Google Cloud Run (GPU-backed, NVIDIA T4)
**Framework:** Faster-Whisper (CTranslate2 backend) — 4× faster than original Whisper at identical accuracy

### 3.2 Why Whisper Over Google Speech-to-Text for This Problem

The choice is deliberate and defensible to judges:

| Criterion | Whisper Large-v3 | Google STT v2 |
|---|---|---|
| Training data | 680,000 hrs, 99 languages, real-world audio | Proprietary, clean audio emphasis |
| Indian dialect coverage | Strong — includes regional accents, code-switching | Strong on standard Hindi, weaker on dialects |
| Noise robustness | Explicitly trained on noisy, emotional speech | Optimized for clear speech |
| Panic/distress speech | Handles — trained on diverse emotional registers | Degraded performance |
| Offline / on-device | Possible (edge deployment) | Cloud-only |
| Cost at scale | Fixed infrastructure cost | Per-minute billing (significant at 700K calls/day) |
| Fine-tuning capability | Full fine-tuning on domain data | Limited customization |

**WER benchmarks on Indian emergency-domain speech (estimated from published Whisper evaluations):**
- Clean Hindi: ~5–8% WER
- Noisy / emotional Hindi: ~12–18% WER
- Mixed Hindi-English (Hinglish): ~10–14% WER

These WER numbers are sufficient because CrisisLink's downstream Gemini classification is **intent-extraction**, not verbatim transcription. "Papa saans nahi aa rahi, gir gaye" with one word missed still classifies as CARDIAC / CRITICAL reliably.

### 3.3 Faster-Whisper Deployment on Cloud Run

```dockerfile
FROM nvidia/cuda:11.8-cudnn8-runtime-ubuntu22.04

RUN pip install faster-whisper fastapi uvicorn google-cloud-pubsub

COPY whisper_service.py .

CMD ["uvicorn", "whisper_service.py:app", "--host", "0.0.0.0", "--port", "8080"]
```

```python
# whisper_service.py (core logic)
from faster_whisper import WhisperModel

model = WhisperModel(
    "large-v3",
    device="cuda",
    compute_type="float16"      # FP16 on T4 — 2× speed vs FP32
)

async def transcribe_chunk(audio_bytes: bytes) -> dict:
    segments, info = model.transcribe(
        audio_bytes,
        beam_size=5,
        language=None,           # Auto-detect language
        vad_filter=True,         # Voice activity detection — ignore silence
        vad_parameters={
            "min_silence_duration_ms": 300
        }
    )
    return {
        "text": " ".join([s.text for s in segments]),
        "language": info.language,
        "language_probability": info.language_probability,
        "segments": [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
    }
```

**Latency profile (Cloud Run, T4 GPU):**
- Model load (cold start): ~8–12 seconds → mitigated by minimum 1 instance always warm
- Inference per 500ms audio chunk: ~600–900ms (FP16, faster-whisper)
- End-to-end chunk latency: ~1.1–1.4 seconds

### 3.4 Fallback: Google Speech-to-Text v2

If Whisper Cloud Run health check fails or p95 latency exceeds 3 seconds (monitored via Cloud Monitoring), the ingestion service routes chunks to Google STT v2 streaming API:

```python
from google.cloud import speech

client = speech.SpeechClient()
config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=16000,
    language_code="hi-IN",             # Dynamically set after first chunk detection
    alternative_language_codes=[
        "pa-IN", "ta-IN", "bn-IN",
        "mr-IN", "te-IN", "gu-IN"
    ],
    enable_automatic_punctuation=True,
    model="latest_long"
)
```

Fallback engages within one missed Whisper response cycle (~1.5 seconds).

### 3.5 Rolling Transcript Accumulation

Individual chunk transcripts are accumulated into a rolling transcript in Firebase:

```
/calls/{call_id}/
    transcript_segments: [
        { text: "mere papa", ts: 1714293601.2, lang: "hi", confidence: 0.94 },
        { text: "gir gaye", ts: 1714293601.9, lang: "hi", confidence: 0.91 },
        { text: "unhe saans nahi aa rahi", ts: 1714293602.7, lang: "hi", confidence: 0.88 }
    ]
    rolling_transcript: "mere papa gir gaye unhe saans nahi aa rahi"
    detected_language: "hi"
    transcript_word_count: 9
```

Gemini is triggered when `transcript_word_count >= 8` — enough context for reliable intent extraction.

---

## 4. Layer 3 — AI Intelligence Layer

### 4.1 Model: Gemini 1.5 Pro via Gemini Live API

**Why Gemini 1.5 Pro (not Gemini Flash):**
- 1.5 Pro has significantly better instruction-following on structured JSON output
- Better multilingual understanding, especially for code-switched Indian speech
- Superior reasoning on ambiguous or partial transcripts
- Flash is used only for the caller guidance generation (latency-critical, lower complexity)

### 4.2 Intelligence Pipeline Architecture

The intelligence layer runs three parallel Gemini calls immediately upon transcript trigger:

```
Rolling transcript available (word_count >= 8)
            │
    ┌───────┼───────┐
    ↓       ↓       ↓
[Call A] [Call B] [Call C]
Triage  Caller   Guidance
Class.  State    Proto-
        Detect.  select.
    └───────┼───────┘
            ↓
   Results merged into
   unified incident object
            ↓
   Pushed to Firebase:
   /calls/{call_id}/incident
```

All three calls are fired concurrently via `asyncio.gather()`. Total latency = slowest of the three, not sum.

### 4.3 Call A: Emergency Classification

**Model:** `gemini-1.5-pro-latest`
**Temperature:** 0.1 (near-deterministic for classification)
**Max output tokens:** 512

**System prompt:**
```
You are an emergency triage AI for India's 112 unified emergency service.
You receive real-time transcripts of incoming emergency calls.
Transcripts may be incomplete, noisy, or contain regional dialects.
Your job is to extract structured emergency intelligence from whatever transcript is available.

Rules:
- Always output valid JSON. Never add explanation outside the JSON.
- If information is missing, use null — never guess.
- confidence reflects your certainty given the transcript quality and length.
- key_facts must be direct extractions or safe inferences — no hallucination.
- If transcript is too short or ambiguous, set emergency_type to "UNKNOWN" and confidence below 0.5.
```

**User prompt:**
```
Transcript: "{rolling_transcript}"
Detected language: "{detected_language}"
Transcript length: {word_count} words
Call duration so far: {seconds}s

Output JSON:
{
  "emergency_type": "MEDICAL|FIRE|CRIME|ACCIDENT|DISASTER|UNKNOWN",
  "emergency_subtype": "CARDIAC|STROKE|TRAUMA|FIRE_STRUCTURAL|FIRE_VEHICLE|ASSAULT|RAPE|THEFT|RTA|FLOOD|STAMPEDE|OTHER|null",
  "severity": "CRITICAL|HIGH|MODERATE|LOW",
  "caller_state": "PANIC_HIGH|PANIC_MED|CALM|INCOHERENT|SILENT",
  "caller_role": "VICTIM|BYSTANDER|WITNESS|UNKNOWN",
  "victim_count": "integer or null",
  "location_clues": ["array of location words or phrases extracted"],
  "key_facts": ["array of critical facts extracted"],
  "guidance_protocol": "CPR|FIRE_EVACUATION|WOUND_CONTROL|STROKE_RESPONSE|DROWNING|STAY_CALM|UNKNOWN",
  "confidence": 0.0-1.0,
  "triage_reasoning": "one sentence explanation of classification"
}
```

**Example input/output:**

Input transcript: `"mere papa gir gaye unhe saans nahi aa rahi"`

```json
{
  "emergency_type": "MEDICAL",
  "emergency_subtype": "CARDIAC",
  "severity": "CRITICAL",
  "caller_state": "PANIC_HIGH",
  "caller_role": "BYSTANDER",
  "victim_count": 1,
  "location_clues": [],
  "key_facts": ["male victim (papa)", "collapsed", "not breathing"],
  "guidance_protocol": "CPR",
  "confidence": 0.91,
  "triage_reasoning": "Caller reports father collapsed and not breathing — classic cardiac arrest presentation"
}
```

### 4.4 Call B: Caller State Intelligence

**Model:** `gemini-1.5-flash` (lower latency acceptable for this task)
**Temperature:** 0.2

This call enriches the caller state beyond the binary panic level into actionable communication parameters:

```
Input: transcript + caller_state from Call A

Output JSON:
{
  "language_register": "SIMPLE|STANDARD|CLINICAL",
  "sentence_length": "SHORT|MEDIUM|LONG",
  "reassurance_needed": true|false,
  "cultural_context": "string or null",
  "comprehension_risk": "HIGH|MEDIUM|LOW",
  "communication_notes": "one sentence"
}
```

This output directly parameterizes the guidance generation in Call C.

**Example output for PANIC_HIGH bystander:**
```json
{
  "language_register": "SIMPLE",
  "sentence_length": "SHORT",
  "reassurance_needed": true,
  "cultural_context": "Use 'aap' respectful form. Avoid English medical terms.",
  "comprehension_risk": "HIGH",
  "communication_notes": "Use maximum 8 words per instruction. Start with reassurance."
}
```

### 4.5 Call C: Guidance Protocol Selection

**Model:** `gemini-1.5-flash`
**Temperature:** 0.3

Selects and retrieves the correct guidance protocol, then parameterizes it for Gemini guidance generation:

```python
PROTOCOL_LIBRARY = {
    "CPR": {
        "source": "Indian Resuscitation Council Guidelines 2022",
        "steps_hi": [
            "Ghabrao mat, main aapke saath hoon",
            "Unhe seedha letao, kisi sakht jagah par",
            "Unke seene ke beech mein apne dono haath rakho",
            "Zyada zyada dabao, 30 baar",
            "Phir unke muh mein do baar saans do",
            "Yahi karte raho jab tak madad na aaye"
        ],
        "steps_en": [...],
        "critical_warnings": ["Do not move if spine injury suspected"],
        "reassurance_phrases_hi": ["Aap bahut accha kar rahe hain", "Madad aa rahi hai"]
    },
    "FIRE_EVACUATION": {...},
    "WOUND_CONTROL": {...},
    "STROKE_RESPONSE": {...},
    "STAY_CALM": {...}
}
```

### 4.6 Guidance Generation

**Model:** `gemini-1.5-pro`
**Temperature:** 0.4 (slight creativity for natural language flow)

```
System: You are a calm emergency guidance AI speaking directly to a distressed caller in India.
You must use ONLY the protocol steps provided. Do not add medical advice beyond the protocol.
Speak as if you are a gentle, confident friend — not a robot.

Caller language: {language}
Caller state: {caller_state}
Communication parameters: {call_b_output}
Protocol: {selected_protocol_steps}

Generate the complete guidance script in {language}.
Keep each instruction under {sentence_length} words.
{"Start with: 'Ghabrao mat, aap sahi kar rahe hain'" if reassurance_needed}
```

Guidance output is streamed token-by-token to the TTS service for minimum time-to-first-audio.

### 4.7 Confidence Gating

```python
def route_by_confidence(classification: dict) -> str:
    if classification["confidence"] >= 0.85:
        return "AUTO_DISPLAY"          # Show to operator, guidance starts
    elif classification["confidence"] >= 0.70:
        return "DISPLAY_WITH_FLAG"     # Show with yellow warning badge
    elif classification["confidence"] >= 0.50:
        return "PARTIAL_DISPLAY"       # Show type only, flag all fields
    else:
        return "OPERATOR_TAKEOVER"     # Hide AI card, alert operator manually
```

### 4.8 Continuous Re-classification

Classification is not a one-shot call. It repeats every 3 seconds as the transcript grows:

```
t=3s  → First classification (word_count >= 8)
t=6s  → Re-classification with more context
t=9s  → Re-classification (usually stabilizes here)
t=12s → Final confirmation or major update
```

If re-classification changes `emergency_type` or `severity`, the operator dashboard shows a live update badge and plays a soft chime. Prior classification is preserved in audit log.

---

## 5. Layer 4 — Dispatch Orchestration Layer

### 5.1 Unit Registry: Firebase Realtime Database

**Schema:**
```json
{
  "units": {
    "{unit_id}": {
      "type": "AMBULANCE|FIRE|POLICE",
      "status": "AVAILABLE|DISPATCHED|ON_SCENE|RETURNING|OFFLINE",
      "location": { "lat": 0.0, "lng": 0.0 },
      "location_updated_at": 1714293600,
      "capabilities": ["CARDIAC", "TRAUMA", "PEDIATRIC", "FIRE_RESCUE"],
      "home_station": "string",
      "affiliated_hospital": "string or null",
      "current_call_id": "string or null"
    }
  }
}
```

Units with `location_updated_at` older than 60 seconds are excluded from dispatch candidates (stale GPS).

### 5.2 Candidate Query

```python
async def get_dispatch_candidates(
    incident_location: dict,
    emergency_type: str,
    required_capabilities: list[str],
    radius_km: float = 15.0
) -> list[dict]:

    # Haversine filter — exclude units beyond radius
    # Firebase doesn't support geo queries natively
    # Geo filtering done in Cloud Run after pulling all AVAILABLE units
    all_available = firebase_db.child("units")\
        .order_by_child("status")\
        .equal_to("AVAILABLE")\
        .get()

    candidates = [
        u for u in all_available
        if haversine(incident_location, u["location"]) <= radius_km
        and u["type"] == emergency_type_to_unit_type(emergency_type)
    ]

    return candidates
```

**Note on geo-filtering:** For production, upgrade to Firestore with GeoHash indexing (GeoFlutterFire) or Typesense for sub-10ms geospatial queries. Firebase Realtime DB geo filtering is done in application layer for MVP — acceptable at demo scale.

### 5.3 ETA Calculation: Google Maps Routes API

```python
async def calculate_etas(
    candidates: list[dict],
    destination: dict
) -> list[dict]:

    async with aiohttp.ClientSession() as session:
        tasks = [
            maps_routes_api(
                origin=c["location"],
                destination=destination,
                travel_mode="DRIVE",
                routing_preference="TRAFFIC_AWARE_OPTIMAL",
                departure_time="now"
            )
            for c in candidates
        ]
        results = await asyncio.gather(*tasks)

    for c, r in zip(candidates, results):
        c["eta_seconds"] = r["routes"][0]["duration"]
        c["distance_meters"] = r["routes"][0]["distanceMeters"]
        c["polyline"] = r["routes"][0]["polyline"]["encodedPolyline"]

    return candidates
```

All ETA calls are fired concurrently. Total latency for 10 candidates: ~400–600ms (Maps API is fast for route lookups).

### 5.4 Composite Ranking Score

```python
def rank_candidates(candidates: list[dict], required_capabilities: list[str]) -> list[dict]:
    for c in candidates:
        eta_score = 1 - min(c["eta_seconds"] / 1800, 1.0)   # Normalize to 0-1 (30min max)
        cap_score = len(
            set(required_capabilities) & set(c["capabilities"])
        ) / max(len(required_capabilities), 1)

        c["rank_score"] = (0.65 * eta_score) + (0.35 * cap_score)

    return sorted(candidates, key=lambda x: x["rank_score"], reverse=True)[:3]
```

ETA is weighted 65%, capability match 35%. Rationale: speed saves lives; capability prevents on-scene escalation. Both matter, but speed is primary.

### 5.5 Dispatch Confirmation & Firebase Update

```python
async def confirm_dispatch(call_id: str, unit_id: str, operator_id: str):
    async with firebase_db.transaction():
        firebase_db.child(f"units/{unit_id}").update({
            "status": "DISPATCHED",
            "current_call_id": call_id
        })
        firebase_db.child(f"calls/{call_id}/dispatch").set({
            "unit_id": unit_id,
            "dispatched_by": operator_id,
            "dispatched_at": time.time(),
            "ai_recommended": True  # or False if operator chose different unit
        })

    await send_push_notification(unit_id, call_id)
    await notify_operator_dashboard(call_id, "DISPATCH_CONFIRMED")
```

Transaction ensures unit status and call dispatch record update atomically — no double-dispatch race condition.

---

## 6. Layer 5 — Caller Guidance Layer

### 6.1 Text-to-Speech: Google Cloud TTS Neural2

**Why Neural2 over standard voices:**
- Natural prosody — essential for panic situations where robotic voice increases distress
- Available in Hindi (hi-IN, 2 voices), Tamil (ta-IN), Bengali (bn-IN), Telugu (te-IN), Marathi (mr-IN)
- SSML support for pace control (slow speech for PANIC_HIGH callers)

```python
from google.cloud import texttospeech

LANGUAGE_VOICE_MAP = {
    "hi": texttospeech.VoiceSelectionParams(
        language_code="hi-IN",
        name="hi-IN-Neural2-A",      # Female, calm
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
    ),
    "ta": texttospeech.VoiceSelectionParams(language_code="ta-IN", name="ta-IN-Neural2-A"),
    "bn": texttospeech.VoiceSelectionParams(language_code="bn-IN", name="bn-IN-Neural2-A"),
    # ... etc
}

PANIC_AUDIO_CONFIG = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3,
    speaking_rate=0.82,     # 18% slower for high panic
    pitch=-1.0              # Slightly lower = more calming
)

CALM_AUDIO_CONFIG = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3,
    speaking_rate=1.0,
    pitch=0.0
)
```

### 6.2 SSML Pacing for Emergency Guidance

```xml
<speak>
  <prosody rate="slow" pitch="-2st">
    Ghabrao mat.
    <break time="800ms"/>
    Main aapke saath hoon.
    <break time="600ms"/>
    Unhe seedha letao.
    <break time="500ms"/>
    Kisi sakht jagah par.
    <break time="1000ms"/>
    Ab apne dono haath unke seene ke beech rakho.
    <break time="500ms"/>
    Zyada zyada dabao.
  </prosody>
</speak>
```

Pauses are critical — a panicked person cannot process continuous speech. 500–1000ms gaps between instructions are clinically recommended.

### 6.3 Guidance Streaming Pipeline

```
Gemini guidance text (streaming tokens)
        ↓
Sentence boundary detection (period / danda / pause marker)
        ↓
Complete sentence → TTS synthesis request (Google Cloud TTS)
        ↓
MP3 audio returned (~200ms for short sentence)
        ↓
Audio queued for playback to caller
        ↓
Simultaneous: next Gemini sentence being synthesized
```

First audio reaches caller within ~1.5 seconds of guidance generation start. Subsequent sentences are pre-synthesized and queued — no gaps between instructions.

---

## 7. Layer 6 — Presentation Layer

### 7.1 Framework: Flutter

Single codebase targeting:
- **Web** (operator dashboard) — Chrome/Edge on desktop workstation
- **Mobile Android** (field responder app) — minimum Android 8.0
- **Web (admin)** — same codebase, role-gated views

### 7.2 State Management: Riverpod + Firebase Streams

```dart
// Real-time incident stream for operator dashboard
final incidentProvider = StreamProvider.family<Incident, String>((ref, callId) {
  return FirebaseDatabase.instance
      .ref('calls/$callId/incident')
      .onValue
      .map((event) => Incident.fromJson(
          Map<String, dynamic>.from(event.snapshot.value as Map)
      ));
});

// Dispatch candidates stream
final dispatchCandidatesProvider = StreamProvider.family<List<Unit>, String>((ref, callId) {
  return FirebaseDatabase.instance
      .ref('calls/$callId/dispatch_candidates')
      .onValue
      .map((event) => (event.snapshot.value as List)
          .map((u) => Unit.fromJson(Map<String, dynamic>.from(u)))
          .toList()
      );
});
```

No polling. All UI updates are push-based via Firebase streams.

### 7.3 Operator Dashboard UI Structure

```
OperatorDashboardScreen
├── CallStatusBar (call duration, caller phone, AI processing indicator)
├── TriageCard (emergency_type, severity badge, key_facts, confidence meter)
│   ├── OverrideButton (inline edit of any field)
│   └── ReasoningTooltip (triage_reasoning from Gemini)
├── DispatchPanel
│   ├── UnitCard × 3 (unit_id, type, ETA, capabilities, rank_score)
│   └── DispatchConfirmButton (primary action — full width, RED for Critical)
├── CallerGuidanceIndicator
│   ├── ProtocolBadge (CPR / FIRE / etc.)
│   ├── CurrentInstructionText (live Gemini output)
│   └── PauseGuidanceButton
└── IncidentLogSidebar (audit trail, real-time)
```

### 7.4 Responder App UI Structure

```
ResponderHomeScreen
├── ActiveDispatchBanner (if dispatched)
└── AvailabilityToggle

DispatchDetailScreen
├── EmergencyTypeBadge
├── SeverityIndicator
├── AIFactsSummary (key_facts from Gemini)
├── NavigationButton (launches Google Maps with encoded polyline)
├── StatusUpdateButtons (En Route / On Scene / Returning)
└── CallOperatorButton
```

---

## 8. Firebase Realtime Database Schema

```json
{
  "calls": {
    "{call_id}": {
      "started_at": 1714293600,
      "caller_number": "REDACTED_HASH",
      "operator_id": "OP_007",
      "status": "ACTIVE|DISPATCHED|CLOSED",

      "transcript_segments": [...],
      "rolling_transcript": "string",
      "detected_language": "hi",
      "transcript_word_count": 12,

      "incident": {
        "emergency_type": "MEDICAL",
        "emergency_subtype": "CARDIAC",
        "severity": "CRITICAL",
        "caller_state": "PANIC_HIGH",
        "caller_role": "BYSTANDER",
        "victim_count": 1,
        "location_clues": [],
        "key_facts": ["male victim", "collapsed", "not breathing"],
        "guidance_protocol": "CPR",
        "confidence": 0.91,
        "triage_reasoning": "string",
        "classified_at": 1714293605,
        "classification_version": 3
      },

      "dispatch_candidates": [...],

      "dispatch": {
        "unit_id": "AMB_007",
        "dispatched_at": 1714293607,
        "dispatched_by": "OP_007",
        "ai_recommended": true,
        "eta_seconds": 360
      },

      "guidance": {
        "protocol": "CPR",
        "language": "hi",
        "status": "ACTIVE|PAUSED|COMPLETED",
        "current_step": 3,
        "total_steps": 6
      },

      "operator_overrides": [
        {
          "field": "severity",
          "original": "HIGH",
          "corrected": "CRITICAL",
          "timestamp": 1714293606,
          "operator_id": "OP_007"
        }
      ]
    }
  },

  "units": { "...": {} },

  "operators": {
    "{operator_id}": {
      "name": "string",
      "station": "string",
      "active_call_id": "string or null",
      "shift_started_at": 1714293000
    }
  }
}
```

---

## 9. Cloud Infrastructure

### 9.1 Google Cloud Services Used

| Service | Purpose | Config |
|---|---|---|
| Cloud Run | Whisper service, Gemini orchestrator, guidance service | Min 1 instance warm; Whisper = GPU (T4); others = CPU |
| Firebase Realtime Database | Real-time state bus for all layers | Blaze plan; rules-based access |
| Google Cloud Pub/Sub | Audio chunk queue between ingestion and Whisper | crisislink-audio-chunks topic |
| Google Maps Routes API | ETA calculation for dispatch | $5/1000 route requests |
| Google Cloud TTS Neural2 | Caller guidance audio | Neural2 voices, hi-IN, ta-IN, etc. |
| Vertex AI | Async analytics, future fine-tuning | BigQuery ML integration |
| BigQuery | Incident log analytics, model feedback | Streaming inserts from Cloud Run |
| Cloud Monitoring | Latency alerts, Whisper health check | Alert policy: p95 > 3s → trigger fallback |
| Secret Manager | API keys (Gemini, Maps, Twilio) | Referenced by Cloud Run at runtime |

### 9.2 Cloud Run Services

| Service | Image | CPU | Memory | GPU | Min Instances |
|---|---|---|---|---|---|
| whisper-service | custom/faster-whisper | 4 | 8GB | T4 | 1 |
| gemini-orchestrator | custom/gemini-orch | 2 | 4GB | — | 1 |
| guidance-service | custom/guidance | 2 | 4GB | — | 1 |
| ingestion-service | custom/ingest | 1 | 2GB | — | 2 |
| dispatch-service | custom/dispatch | 1 | 2GB | — | 1 |

### 9.3 Environment Variables (via Secret Manager)

```
GEMINI_API_KEY
GOOGLE_MAPS_API_KEY
FIREBASE_DATABASE_URL
FIREBASE_SERVICE_ACCOUNT
GOOGLE_TTS_API_KEY
TWILIO_ACCOUNT_SID (production only)
TWILIO_AUTH_TOKEN (production only)
```

---

## 10. Security Architecture

### 10.1 Firebase Security Rules

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    match /calls/{callId} {
      allow read, write: if request.auth.token.role == "OPERATOR"
          && request.auth.token.station == resource.data.station_id;

      match /dispatch {
        allow write: if request.auth.token.role == "OPERATOR";
        allow read: if request.auth.token.role in ["OPERATOR", "RESPONDER", "ADMIN"];
      }
    }

    match /units/{unitId} {
      allow read: if request.auth.token.role in ["OPERATOR", "ADMIN"];
      allow write: if request.auth.token.uid == resource.data.responder_uid
          || request.auth.token.role == "ADMIN";
    }

    match /analytics/{doc} {
      allow read, write: if request.auth.token.role == "ADMIN";
    }
  }
}
```

### 10.2 Data Security

- All audio streams encrypted in transit (TLS 1.3)
- Audio deleted from Cloud Run memory immediately after Whisper processing
- Transcripts stored with caller number replaced by SHA-256 hash (one-way)
- Operator IDs authenticated via Firebase Auth (Google Sign-In)
- Field responder devices authenticated via Firebase Auth + device fingerprint

### 10.3 DPDP Act 2023 Compliance Notes

- No personal data processed beyond operational necessity
- Caller phone number never stored in plain text
- All data retained per PSAP SOP (90 days minimum for legal purposes)
- Data not shared with third parties
- Audit log maintained for all AI decisions and operator actions

---

## 11. Datasets and Training Data

### 11.1 MVP (Hackathon — No Training Required)

Whisper Large-v3 and Gemini 1.5 Pro are used as pre-trained models. No fine-tuning is required for the hackathon MVP. The following are used only as **prompt-grounding reference data:**

| Dataset / Source | Content | Use in CrisisLink |
|---|---|---|
| Indian Resuscitation Council Guidelines 2022 | CPR, BLS, ACLS protocols | CPR guidance protocol library |
| NDMA India Emergency Management Guidelines | Disaster response SOPs | Fire, flood, stampede protocols |
| MHA 112 India SOP Documentation (public) | Operator workflow standards | Operator UX design, triage categories |
| WHO Emergency Triage Protocols | Medical severity classification | Severity scoring rubric |
| AI4Bharat IndicTrans2 vocabulary | Indian language vocabulary reference | Prompt construction for Indic languages |

### 11.2 Production Fine-tuning Plan (Post-Hackathon)

| Fine-tuning Target | Dataset | Expected Improvement |
|---|---|---|
| Whisper — Indian emergency speech | AI4Bharat IndicSUPERB + IndicVoices (public) | WER reduction ~20–30% on Indian emergency audio |
| Whisper — dialect robustness | Kathbath (IIT Bombay) — 1750 hrs Indian speech | Regional dialect coverage improvement |
| Gemini — emergency classification | Operator override logs (CrisisLink system) | Classification accuracy improvement over time |
| Gemini — guidance quality | Caller outcome data + paramedic review | Protocol adherence and language quality |

### 11.3 Synthetic Demo Data

For the hackathon demo, the following synthetic data is generated:

```python
DEMO_UNITS = [
    {"id": "AMB_007", "type": "AMBULANCE", "location": {"lat": 30.7340, "lng": 76.7820},
     "capabilities": ["CARDIAC", "TRAUMA"], "status": "AVAILABLE", "eta": 360},
    {"id": "AMB_012", "type": "AMBULANCE", "location": {"lat": 30.7290, "lng": 76.7750},
     "capabilities": ["GENERAL"], "status": "AVAILABLE", "eta": 540},
    {"id": "FIRE_003", "type": "FIRE", "location": {"lat": 30.7400, "lng": 76.7900},
     "capabilities": ["FIRE_RESCUE", "EXTRICATION"], "status": "AVAILABLE", "eta": 480},
    {"id": "POL_021", "type": "POLICE", "location": {"lat": 30.7310, "lng": 76.7800},
     "capabilities": ["GENERAL"], "status": "DISPATCHED", "eta": null},
    {"id": "AMB_019", "type": "AMBULANCE", "location": {"lat": 30.7380, "lng": 76.7700},
     "capabilities": ["PEDIATRIC", "TRAUMA"], "status": "AVAILABLE", "eta": 420},
]

DEMO_CALLS = [
    {
        "script_hi": "mere papa gir gaye unhe saans nahi aa rahi please jaldi aao",
        "expected_type": "MEDICAL", "expected_subtype": "CARDIAC",
        "expected_severity": "CRITICAL", "expected_protocol": "CPR"
    },
    {
        "script_hi": "hamare ghar mein aag lag gayi andar log hain",
        "expected_type": "FIRE", "expected_subtype": "FIRE_STRUCTURAL",
        "expected_severity": "CRITICAL", "expected_protocol": "FIRE_EVACUATION"
    }
]
```

---

## 12. API Contracts

### 12.1 POST /transcribe (Whisper Service)

**Request:**
```json
{
  "call_id": "string",
  "chunk_index": 0,
  "audio_b64": "base64_encoded_wav",
  "chunk_duration_ms": 500
}
```

**Response:**
```json
{
  "call_id": "string",
  "chunk_index": 0,
  "text": "mere papa gir gaye",
  "language": "hi",
  "language_probability": 0.97,
  "processing_ms": 820
}
```

### 12.2 POST /classify (Gemini Orchestrator)

**Request:**
```json
{
  "call_id": "string",
  "rolling_transcript": "string",
  "detected_language": "hi",
  "word_count": 12,
  "classification_round": 2
}
```

**Response:** Full incident JSON as defined in Section 4.3.

### 12.3 POST /dispatch/candidates (Dispatch Service)

**Request:**
```json
{
  "call_id": "string",
  "emergency_type": "MEDICAL",
  "required_capabilities": ["CARDIAC"],
  "incident_location": {"lat": 30.7333, "lng": 76.7794},
  "radius_km": 15
}
```

**Response:**
```json
{
  "candidates": [
    {
      "unit_id": "AMB_007",
      "eta_seconds": 360,
      "distance_meters": 2100,
      "rank_score": 0.87,
      "capabilities": ["CARDIAC", "TRAUMA"]
    }
  ]
}
```

---

## 13. Testing Strategy

### 13.1 Unit Tests

- Whisper chunk transcription accuracy on 20 synthetic Hindi audio clips
- Gemini classification on 30 test transcripts (10 cardiac, 10 fire, 10 crime) — measure accuracy vs expected
- Dispatch ranking with mock unit data — verify ETA and capability weighting
- Firebase security rules — verify role-based access

### 13.2 Integration Tests

- Full pipeline: audio in → transcript → classification → dispatch card visible on dashboard (< 10s end-to-end)
- Operator dispatch → Firebase update → responder notification (< 3s)
- Language detection accuracy on Hindi, Punjabi, Tamil test phrases

### 13.3 Demo Rehearsal Checklist

- [ ] Whisper Cloud Run instance pre-warmed (hit /health 10 mins before)
- [ ] Firebase emulator running as local backup
- [ ] Demo audio clips loaded in browser (backup for live mic)
- [ ] Gemini API key quota checked (not near limit)
- [ ] Maps API route pre-cached for demo location
- [ ] Hindi CPR guidance pre-synthesized as audio fallback
- [ ] Operator dashboard open on full screen, dark mode off
- [ ] Responder mobile app open on second device
- [ ] Network: demo on mobile hotspot (not venue WiFi — too unpredictable)

---

*CrisisLink TRD v1.0 — Solution Challenge 2026*
*Thapar Institute of Engineering & Technology*
