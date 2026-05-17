# CrisisLink — Demo Setup & Run Guide

## What Judges Will See

1. A Hindi cardiac arrest call transcript is fed into the Intelligence Service.
2. Gemini 1.5 Pro classifies it in real time: **MEDICAL / CARDIAC / CRITICAL**.
3. The Dispatch Service queries Firebase for available ambulances, calculates Google Maps ETAs, and returns a ranked dispatch card.
4. The operator confirms dispatch with one tap — Firebase updates instantly.
5. The TTS Service synthesises Hindi CPR guidance via Google Cloud Neural2 voices.
6. The Flutter dashboard reflects all updates live via Firebase Realtime Database streams.

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | `python --version` |
| pip | latest | `pip install --upgrade pip` |
| Flutter | 3.2+ | For frontend only |
| bash | any | Git Bash / WSL / macOS Terminal |
| curl + python3 | any | Required by `demo.sh` |

---

## Step 1 — Clone & Install

```bash
git clone <repo-url>
cd CrisisLink-1
pip install -r backend/requirements.txt
```

---

## Step 2 — Configure Environment

```bash
cd backend
cp .env.example .env
```

Open `backend/.env` and fill in:

| Variable | Where to get it |
|---|---|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com) → Get API Key |
| `GOOGLE_MAPS_API_KEY` | [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Routes API |
| `GOOGLE_APPLICATION_CREDENTIALS` | Firebase Console → Project Settings → Service Accounts → Generate new private key → save as `backend/serviceaccount.json` |
| `FIREBASE_DATABASE_URL` | Firebase Console → Realtime Database → copy the URL (`https://your-project-default-rtdb.firebaseio.com`) |

Leave `CRISISLINK_USE_REAL_SERVICES=true` — this activates Gemini, Maps, Firebase, TTS, and FCM.

---

## Step 3 — Start Backend Services

From the project root:

```bash
chmod +x start.sh
./start.sh
```

This starts four FastAPI services:

| Service | Port | Swagger docs |
|---|---|---|
| Speech Ingestion | 8001 | http://localhost:8001/docs |
| Intelligence (Gemini) | 8002 | http://localhost:8002/docs |
| Dispatch (Maps + Firebase) | 8003 | http://localhost:8003/docs |
| TTS (Google Cloud Neural2) | 8004 | http://localhost:8004/docs |

Wait ~5 seconds for all services to print `Application startup complete`.

---

## Step 4 — Run the Demo Flow

In a second terminal:

```bash
chmod +x demo.sh
./demo.sh
```

The script runs four steps automatically:
1. **Classify** — sends the Hindi cardiac arrest transcript to Gemini
2. **Recommend** — gets ranked dispatch candidates with ETAs
3. **Confirm** — dispatches AMB_007, triggers FCM push
4. **TTS** — synthesises Hindi CPR guidance

---

## Step 5 — Start the Flutter Frontend

```bash
cd frontend
flutter run -d chrome \
  --dart-define=CRISISLINK_BACKEND_URL=http://localhost:8003 \
  --dart-define=CRISISLINK_API_TOKEN=crisislink-dev-token \
  --dart-define=FIREBASE_DATABASE_URL=https://your-project-default-rtdb.firebaseio.com
```

The Flutter app opens at **http://localhost:8080** (or the port Flutter prints).

**Three screens accessible:**
- `/` — Operator Dashboard (triage card + dispatch panel)
- `/responder` — Field Responder (navigation + status updates)
- `/admin` — PSAP Admin (analytics, unit management)

---

## Demo Flow Summary (for judges)

```
[demo.sh Step 1]
  Hindi transcript → Intelligence Service (port 8002)
    → Gemini 1.5 Pro classifies: MEDICAL / CARDIAC / CRITICAL / 0.91 confidence
    → Written to Firebase: /calls/demo-001/classification

[demo.sh Step 2]
  Classification → Dispatch Service (port 8003)
    → Firebase unit query + Google Maps ETA calculation
    → Ranked dispatch card returned (top 3 ambulances)
    → Written to Firebase: /calls/demo-001/dispatch_card

[demo.sh Step 3]
  AMB_007 confirmed → Dispatch Service
    → Firebase unit status: available → dispatched
    → FCM push notification sent to responder device
    → Written to Firebase: /calls/demo-001/dispatch

[demo.sh Step 4]
  CPR text → TTS Service (port 8004)
    → Google Cloud Neural2 Hindi synthesis
    → MP3 audio returned

[Flutter Dashboard]
  All Firebase writes above stream to the operator screen in real time (<200ms).
```

---

## Troubleshooting

**`401 Unauthorized` on curl:** Token mismatch — confirm `.env` has `CRISISLINK_API_TOKEN=crisislink-dev-token` and services were restarted after `.env` was edited.

**Gemini returns mock data:** `CRISISLINK_USE_REAL_SERVICES` is not `true`, or `GEMINI_API_KEY` is missing. Check `.env` and restart services.

**Maps ETA is straight-line estimate:** `GOOGLE_MAPS_API_KEY` missing or Routes API not enabled in Cloud Console. Dispatch still works with the fallback.

**Firebase writes not appearing in Flutter:** `FIREBASE_DATABASE_URL` mismatch between backend `.env` and Flutter `--dart-define`. Both must point to the same Firebase project.

**`faster-whisper` install fails on Windows:** The Whisper GPU transcriber is not used in the demo flow — speech is injected directly as text via `demo.sh`. Install failure does not block the demo.
