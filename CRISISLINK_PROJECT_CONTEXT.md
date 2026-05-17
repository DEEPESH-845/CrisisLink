# CrisisLink Project Context

## Purpose

This file is the handoff context for future chats. It records the project audit, missing pieces, implementation work completed, verification results, and remaining work.

## Audit Snapshot

Date: 2026-05-02

The repository contains a CrisisLink emergency-response MVP with:

- Python FastAPI backend services for speech ingestion, intelligence, dispatch, TTS, and integration helpers.
- Flutter frontend for operator, responder, and admin roles.
- Firebase Realtime Database rules and project config.
- Product, technical, architecture, pitch, and blueprint documents.
- A large backend unit/property test suite.

## Main Audit Findings

- Backend services were strongly tested but defaulted to mocks/in-memory implementations.
- Production adapters for Whisper, Gemini, Firebase RTDB, BigQuery, Google Maps, Pub/Sub, and FCM were incomplete or placeholders.
- Frontend Firebase config and backend auth token were placeholders.
- Frontend admin/audit services called backend endpoints that did not exist.
- Responder app listened to `/units/{unit_id}/dispatch`, but dispatch confirmation did not write that assignment.
- Transcript schema was inconsistent: frontend expected a string while some backend writers wrote an object with `text`.
- Frontend app entry only launched the operator dashboard; responder and admin screens existed but were not routable.
- Backend production dependency list missed several packages used by intended integrations.
- Full backend tests could not run because `hypothesis` was not installed in the environment; non-property tests passed.
- Flutter verification could not run because `flutter` was not installed or not on PATH.

## Implementation Log

### 2026-05-02

- Created this context file.
- Added production-oriented backend dependencies for Google TTS, Gemini, and HTTP Maps calls.
- Implemented BigQuery audit logging path with environment-based project configuration.
- Replaced Firebase writer placeholders with RTDB write implementations that activate when Firebase Admin is configured and still fail safely in local/test mode.
- Added environment toggle `CRISISLINK_USE_REAL_SERVICES=true` for dispatch, intelligence, and TTS services.
- Added Google Routes API ETA client and Firebase FCM notification client.
- Added dispatch assignment writing to `/units/{unit_id}/dispatch` so responder apps can receive full assignment details from RTDB.
- Added missing backend endpoints used by frontend:
  - `POST /api/v1/audit/log`
  - `GET /api/v1/analytics/response-times`
  - `GET /api/v1/analytics/classification-accuracy`
  - `GET /api/v1/analytics/trend-reports`
  - `POST /api/v1/analytics/record-override`
- Updated frontend backend URL and API token to use Dart defines with local defaults.
- Wired frontend routes for operator (`/`), responder (`/responder`), and admin (`/admin`).
- Made frontend Firebase options configurable via Dart defines instead of hardcoded placeholder strings.
- Fixed transcript stream parsing so the frontend accepts both string transcripts and object payloads with `text`.
- Hardened nested Firebase map parsing in Dart models.
- Extended dispatch confirmation payload so case context can travel to responder notifications/assignments.

## Verification Log

- Previous audit non-property backend tests: `396 passed`.
- Previous full backend test attempt: failed at collection because `hypothesis` was missing.
- Previous frontend analysis attempt: failed because `flutter` was unavailable.
- 2026-05-02 targeted backend regression suite after changes: `161 passed`.
- 2026-05-02 broad non-property backend suite after changes: `396 passed`.
- 2026-05-02 Flutter analysis retry: failed because `flutter` is not recognized on PATH.
- 2026-05-02 git status showed modified backend/frontend files and new `CRISISLINK_PROJECT_CONTEXT.md`; `CrisisLink_PRD.md` and `CrisisLink_TRD.md` remain untracked from the original audit state.

## Remaining Work

- Run backend regression tests after the implementation pass.
- Flutter verification still depends on Flutter being available on PATH.
- Replace the demo GPS position provider with a real geolocation package for mobile builds.
- Add real Whisper/Faster-Whisper implementation or a Google STT fallback adapter for production speech ingestion.
- Add actual BigQuery aggregation queries behind the analytics endpoints; current endpoints return safe empty-state data.
