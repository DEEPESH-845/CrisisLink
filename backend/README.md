# CrisisLink Backend Services

Backend services for the CrisisLink Emergency AI Co-Pilot, built with Python FastAPI.

## Services

- **speech_ingestion/** — Speech Ingestion Service: audio chunking, Whisper transcription, STT fallback
- **intelligence/** — Intelligence Service: Gemini-powered emergency classification, caller state detection, guidance generation
- **dispatch/** — Dispatch Service: unit filtering, ETA calculation, composite scoring, dispatch confirmation
- **tts/** — TTS Service: Google Cloud TTS Neural2 voice synthesis

## Shared

- **shared/** — Shared Pydantic data models, Firebase utilities, and common helpers

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Testing

```bash
pytest
```
