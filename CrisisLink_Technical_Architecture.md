# CrisisLink — Technical Architecture
## Full Stack, AI Pipeline, Data Strategy & Model Rationale

---

## Architecture Overview

CrisisLink is a **real-time AI orchestration system** built on four layers:

```
CALLER → [Speech Layer] → [Intelligence Layer] → [Dispatch Layer] → [Guidance Layer]
                                    ↕
                          [Operator Dashboard]
                                    ↕
                          [Field Responder App]
                                    ↕
                          [Admin Analytics Layer]
```

Every layer runs in parallel from the moment a call connects. Total time to first AI output: **< 5 seconds.**

---

## Layer 1 — Speech Ingestion & Transcription

### Primary Model: OpenAI Whisper (Large-v3)

**Why Whisper over Google Speech-to-Text:**

| Criterion | Whisper Large-v3 | Google STT |
|---|---|---|
| Indian language support | 99 languages including all major Indian ones | Strong but narrower dialect coverage |
| Noise robustness | Trained on noisy real-world audio | Cleaner audio assumed |
| Dialect handling | Significantly stronger on regional accents | Standard accents preferred |
| Offline capability | Can run on-device / edge | Cloud-only |
| Panic speech accuracy | Strong — trained on diverse emotional speech | Moderate |
| Cost | Open source / self-hostable | Per-minute billing |

Whisper Large-v3 is specifically chosen because **emergency calls are the worst-case audio scenario** — crying, shouting, background chaos, regional dialects, broken sentences. Whisper was trained on 680,000 hours of multilingual audio explicitly including noisy, emotional, non-studio speech.

**Deployment:** Whisper runs on **Google Cloud Run** with a GPU-backed container (NVIDIA T4). Transcription latency at Large-v3: ~1.2–1.8s for a 5-second audio chunk. Streaming transcription via chunked audio pipeline.

### Streaming Pipeline

```
Caller audio (WebRTC / SIP bridge)
        ↓
Chunked audio buffer (500ms chunks)
        ↓
Whisper Large-v3 on Cloud Run (GPU)
        ↓
Streaming transcript → Firebase Realtime DB
        ↓
Gemini receives transcript as it builds
```

This means Gemini starts processing intent **before the caller finishes speaking.**

### Fallback: Google Speech-to-Text v2

If Whisper latency spikes above 3s (measured via Cloud Monitoring), the pipeline auto-routes to Google STT v2 as fallback. The operator never sees this switch.

---

## Layer 2 — Intelligence & Classification (Gemini)

### Model: Gemini 1.5 Pro / Gemini Live API

Gemini receives the rolling Whisper transcript and performs three simultaneous tasks:

#### Task A: Emergency Classification

**Prompt structure (system context):**
```
You are an emergency triage AI for India's 112 system.
Given the transcript below, output a JSON object with:
- emergency_type: one of [MEDICAL, FIRE, CRIME, ACCIDENT, DISASTER, UNKNOWN]
- severity: one of [CRITICAL, HIGH, MODERATE, LOW]
- caller_state: one of [PANIC_HIGH, PANIC_MED, CALM, INCOHERENT]
- caller_role: one of [VICTIM, BYSTANDER, WITNESS]
- language_detected: ISO code
- key_facts: array of extracted facts (location clues, symptoms, numbers)
- confidence: float 0-1

Respond only in valid JSON. Be fast — human life depends on latency.
Transcript: {rolling_transcript}
```

Output is streamed to Firebase as partial JSON, so the operator dashboard updates token-by-token.

#### Task B: Caller State Adaptation

Based on `caller_state` and `caller_role`, Gemini selects a **guidance register:**

- `PANIC_HIGH + VICTIM` → Ultra-simple, short sentences, reassurance-first
- `PANIC_HIGH + BYSTANDER` → Directive, numbered steps, no medical jargon
- `CALM + BYSTANDER` → Full clinical protocol
- `INCOHERENT` → Operator flagged for direct takeover

#### Task C: Guidance Generation

Gemini generates caller instructions in the **detected language** using a protocol-grounded prompt:

```
You are guiding a bystander through a cardiac emergency in India.
The caller speaks {language}. Their panic level is {panic_level}.
Provide step-by-step CPR guidance. Use simple words. Short sentences.
Start with reassurance. Do not use medical terminology.
Generate in {language} script (not transliteration).
```

Guidance is streamed to a text-to-speech layer (Google Cloud TTS — Neural2 voices, available in Hindi, Tamil, Telugu, Bengali, Marathi) and played to the caller via the telephony bridge.

### Why Gemini for Intelligence (not a fine-tuned classifier)

A traditional ML classifier (BERT, fine-tuned) would give faster single-label classification but cannot:
- Extract structured facts from free-form panicked speech
- Generate adaptive multilingual guidance
- Handle ambiguous, incomplete, or context-dependent emergencies
- Generalize to novel emergency types without retraining

Gemini's instruction-following capability handles all of these in a single model call.

---

## Layer 3 — Dispatch Intelligence

### Unit Availability: Firebase Realtime Database

```json
{
  "units": {
    "AMB_007": {
      "type": "ambulance",
      "status": "available",
      "location": { "lat": 30.7333, "lng": 76.7794 },
      "hospital": "PGIMER Chandigarh",
      "capabilities": ["cardiac", "trauma", "pediatric"],
      "last_updated": 1714293600
    }
  }
}
```

Units push GPS location every 10 seconds via Flutter background service. Status transitions: `available → dispatched → on_scene → returning → available`.

### Routing: Google Maps Routes API

For each available unit within 15km radius, CrisisLink calls the Routes API with:
- Real-time traffic conditions
- Emergency vehicle routing (avoid certain road types)
- ETA with confidence interval

Top 3 units ranked by: `score = (0.6 × ETA) + (0.4 × capability_match)`

Capability match checks whether unit has the specific equipment needed for the classified emergency type.

### Dispatch Flow

```
Emergency classified (Gemini output)
        ↓
Query Firebase: units with status=available within 15km
        ↓
Google Maps Routes API: calculate ETA for each
        ↓
Rank by composite score
        ↓
Operator sees ranked card → one tap confirms
        ↓
Firebase updates unit status to dispatched
        ↓
Flutter notification pushed to field responder
        ↓
Google Maps turn-by-turn begins on responder device
```

Total time from classification to operator seeing dispatch card: **< 2 seconds.**

---

## Layer 4 — Operator Dashboard

### Stack: Flutter Web + Firebase Streams

The operator dashboard is a **Flutter Web** app receiving Firebase real-time streams. No polling. No refresh. State updates propagate in < 200ms.

**Dashboard components:**

```
┌─────────────────────────────────────────────────────┐
│ ACTIVE CALL — 14:32:07                              │
│                                                     │
│ CARDIAC — CRITICAL          Confidence: 0.94        │
│ Caller: HIGH PANIC / Bystander / Female             │
│ Language: Hindi                                     │
│                                                     │
│ Key facts:                                          │
│  • "Papa" — likely older male victim               │
│  • "Gir gaye" — fallen, unresponsive               │
│  • Location clue: "ghar ke andar" (inside home)    │
│                                                     │
│ ┌─────────────────────────────────────────────┐    │
│ │ AMB-007 · PGIMER · ETA 6 min · Cardiac ✓   │    │
│ │ AMB-012 · GMC-32 · ETA 9 min · General     │    │
│ │                    [ DISPATCH AMB-007 ]     │    │
│ └─────────────────────────────────────────────┘    │
│                                                     │
│ Caller guidance: Hindi CPR → Active                 │
└─────────────────────────────────────────────────────┘
```

All fields populate from Firebase streams. The operator's only action is the dispatch tap.

---

## Layer 5 — Analytics (Vertex AI)

**Vertex AI AutoML + BigQuery** ingests incident logs for:

- Response time trend analysis by region, time of day, emergency type
- Unit utilization and dead zone identification
- False classification rate monitoring (operator override = negative label)
- Predictive unit pre-positioning (high-incident zones get units repositioned before peak hours)

Dashboards built in **Looker Studio** connected to BigQuery. PSAP admins see live and historical data in the same Flutter admin panel.

---

## Data Strategy

### No Patient Data Required for MVP

CrisisLink's MVP requires **zero real patient data.** The AI models (Whisper, Gemini) are pre-trained. The system only needs:

1. Simulated unit location data (generated)
2. Simulated call transcripts (generated for demo)
3. Protocol datasets (publicly available)

### Emergency Protocol Datasets

| Dataset | Source | Use |
|---|---|---|
| Indian Emergency Medical Protocols | NHA / AIIMS published guidelines | Gemini system prompt grounding |
| CPR & BLS Guidelines | Indian Resuscitation Council 2022 | Cardiac guidance generation |
| Fire Safety Evacuation Protocols | NDMA India | Fire guidance generation |
| 112 India SOP documentation | MHA public documents | Operator workflow design |
| Whisper training data | OpenAI (680K hrs multilingual) | Pre-trained — no fine-tuning needed for MVP |

### For Production (Post-Hackathon)

| Data Type | Source | Purpose |
|---|---|---|
| Anonymized call transcripts | 112 state PSAPs (via MoU) | Fine-tune Whisper on Indian emergency speech |
| Operator override logs | CrisisLink system | Improve Gemini classification accuracy |
| Response time outcomes | Dispatch logs | Train predictive pre-positioning model |
| Regional dialect audio | Kaggle / AI4Bharat corpus | Dialect robustness for Whisper |

**AI4Bharat** (IIT Madras) has the largest open-source Indian language speech corpus — IndicSUPERB, IndicVoices — directly usable for fine-tuning post-hackathon.

---

## Addressing the Core Practical Challenge

### "Will AI actually understand panicked emergency calls well enough?"

This is the right question. Here is the honest technical answer:

**Whisper Large-v3 on emergency speech:**
- Trained on 680,000 hours including broadcast news, podcasts, phone calls, and noisy real-world audio
- Word Error Rate (WER) on Hindi: ~8–12% — sufficient for intent extraction even if every word isn't perfect
- Panic speech degrades WER by ~15–20% — but Gemini's classification is **intent-based not word-perfect** — "papa saans nahi" is enough signal even if a word is missed

**Gemini on incomplete transcripts:**
- The classification prompt is designed for **partial and noisy input** — it extracts intent from fragments
- Confidence score is always shown — if confidence < 0.7, operator is flagged to take manual control
- The system **assists, not replaces** — operator always has override authority

**The honest MVP position:**
> CrisisLink does not claim 100% accuracy. It claims to reduce the operator's parallel cognitive load from 6 simultaneous tasks to 1 confirmation decision — and to start helping the caller in parallel, not after dispatch.

Even at 80% classification accuracy, the parallel caller guidance and one-tap dispatch represent a step-change improvement over the current zero-AI baseline.

---

## Tech Stack Summary

| Component | Technology | Justification |
|---|---|---|
| Speech transcription | Whisper Large-v3 (Cloud Run GPU) | Best noise/dialect robustness for Indian emergency audio |
| Fallback STT | Google Speech-to-Text v2 | Latency safety net, Google native |
| Intelligence & triage | Gemini 1.5 Pro (Gemini Live API) | Multilingual, generative, instruction-following |
| Caller guidance TTS | Google Cloud TTS Neural2 | Natural voice in Indian languages |
| Real-time state | Firebase Realtime Database | Sub-200ms sync across all user roles |
| Dispatch routing | Google Maps Routes API | Live traffic, ETA, emergency routing |
| Backend orchestration | Google Cloud Run (Python FastAPI) | Serverless, auto-scaling, GPU support |
| Frontend | Flutter (Web + Mobile) | Single codebase, 3 user roles |
| Analytics | Vertex AI + BigQuery + Looker | Production-grade, Google-native |
| Telephony bridge | Twilio Voice API / Exotel (India) | SIP/WebRTC to web audio pipeline |

---

## Security & Compliance

- All call audio and transcripts encrypted at rest (AES-256) and in transit (TLS 1.3)
- Firebase Security Rules restrict operator/responder/admin data access by role
- No call audio stored beyond session — transcripts retained for 90 days per PSAP SOP
- DPDP Act 2023 (India) compliant — no personal data processed without operational necessity
- Audit log of every AI classification and operator override stored in BigQuery

---

## Build Phases for Hackathon

**Phase 1 — Core demo (48 hours)**
- Whisper + Gemini pipeline with simulated call input
- Firebase unit availability with 5 simulated units
- Operator dashboard (Flutter Web) receiving live AI triage card
- One-tap dispatch flow

**Phase 2 — Demo polish (next 24 hours)**
- Hindi CPR guidance TTS playback in demo
- Google Maps ETA display on operator card
- Field responder Flutter mobile view
- Admin dashboard with mock analytics

**Phase 3 — Submission**
- GitHub repo with clean README
- 3-minute demo video (Hindi call → live triage → dispatch → CPR guidance)
- Architecture diagram
- Prototype live link (Cloud Run deployment)

---

*CrisisLink — Solution Challenge 2026*
*Thapar Institute of Engineering & Technology*
