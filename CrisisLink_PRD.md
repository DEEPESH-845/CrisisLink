# CrisisLink — Product Requirements Document (PRD)
**Version:** 1.0
**Date:** April 2026
**Author:** Prabinder Singh, Thapar Institute of Engineering & Technology
**Hackathon:** Solution Challenge 2026 — Google Developers × Hack2Skill
**Track:** Rapid Crisis Response — Open Innovation

---

## 1. Executive Summary

CrisisLink is an AI co-pilot for India's 112 emergency response infrastructure. It inserts a real-time intelligence layer between the moment a distressed caller connects and the moment a unit is dispatched — collapsing what is currently a 8–14 minute serial human process into a sub-5-second AI-assisted decision.

The product does not replace the 112 operator. It removes every task except the final dispatch confirmation, freeing the operator to focus on caller empathy while AI handles classification, routing, and parallel caller guidance simultaneously.

**Core value proposition:** Every second saved in triage is a second closer to survival. CrisisLink targets a 60–70% reduction in time-to-dispatch for the first AI-assisted triage decision.

---

## 2. Problem Statement

### 2.1 Context

India's 112 emergency number is the unified access point for police, fire, and ambulance services across all states. It handles approximately **700,000 calls per day** — roughly 8 calls per second at peak.

### 2.2 The Gap

When a panicked caller dials 112 today, a human operator must perform the following tasks **serially and manually:**

1. Identify the language the caller is speaking
2. Understand the emergency through panic, dialect, broken speech
3. Determine emergency type and severity
4. Manually search for nearest available unit
5. Contact dispatch separately (often by radio or internal phone)
6. Keep the caller calm and on the line
7. Log the incident

This process takes **8–14 minutes on average.** The medical reality:

- Cardiac arrest: brain death begins at **6 minutes**
- Severe bleeding: unconsciousness from blood loss in **3–5 minutes**
- Fire: lethal smoke inhalation in **4 minutes**
- Stroke: every 1-minute delay = **1.9 million neurons lost**

The gap is not infrastructure. It is **intelligence.** There is no AI layer assisting operators anywhere in India's 112 system today.

### 2.3 Why Existing Solutions Fail

| Existing Approach | Gap |
|---|---|
| Human operator only | Serial processing, no AI, language-dependent, fatigue-prone |
| Basic IVR systems | Cannot handle free-form panicked speech, no intelligence |
| CAD (Computer-Aided Dispatch) | Exists in some states but requires manual operator input — no AI triage |
| Foreign AI dispatch systems | Not trained on Indian languages, dialects, or emergency protocols |

---

## 3. Goals and Non-Goals

### 3.1 Goals

- Reduce time-to-dispatch for first AI-assisted triage to under **4 minutes**
- Provide real-time multilingual emergency classification across **22+ Indian languages**
- Generate AI-guided caller support in parallel with dispatch (not after)
- Deliver a single cross-platform app for operators, field responders, and PSAP admins
- Demonstrate a live working prototype with a Hindi cardiac arrest call as the proof case

### 3.2 Non-Goals (Hackathon Scope)

- Full integration with actual 112 PSAP telephony infrastructure
- Real patient data or clinical validation
- Autonomous dispatch without operator confirmation
- Hardware IoT sensor integration
- Payment or billing systems

---

## 4. Users and Personas

### 4.1 Primary User: 112 Operator (Dispatcher)

**Profile:** Government employee, 22–45 years old, regional language speaker, works in a PSAP (Public Safety Answering Point) control room. Handles 80–120 calls per 8-hour shift. High cognitive load, high burnout rate.

**Current pain:** Spends 60–70% of each call on information gathering rather than empathy and guidance. Language mismatches cause critical delays. No tools assist in real time.

**What CrisisLink gives them:** A pre-filled triage card appears before they finish their first sentence. One tap confirms dispatch. AI handles the caller guidance in parallel. Their only job becomes human oversight.

### 4.2 Secondary User: Field Responder (Ambulance / Fire / Police)

**Profile:** On-ground emergency personnel. Receives dispatch via radio or personal device. Needs precise location, case context, and navigation. Often lacks detailed pre-arrival patient information.

**What CrisisLink gives them:** Instant push notification with case type, AI-extracted facts (patient age, symptoms, location clues), and Google Maps turn-by-turn. No ambiguity on arrival.

### 4.3 Tertiary User: PSAP Administrator

**Profile:** Senior official overseeing a state or district 112 control room. Responsible for resource allocation, performance reporting, and operational planning.

**What CrisisLink gives them:** Real-time incident heatmap, unit utilization rates, response time analytics, AI classification accuracy metrics, and predictive resource pre-positioning recommendations.

---

## 5. User Stories

### Operator
- As a 112 operator, I want to see the emergency type and severity automatically identified so I don't spend the first 2 minutes of a call just understanding what happened.
- As a 112 operator, I want a ranked list of available units with ETAs so I can dispatch with one tap instead of making separate calls.
- As a 112 operator, I want to know the caller's panic level and language automatically so I can focus on empathy instead of identification.
- As a 112 operator, I want the AI to guide the caller simultaneously with dispatch so I'm not choosing between the two.

### Field Responder
- As a field responder, I want push notification with case context the moment I'm dispatched so I can prepare en route.
- As a field responder, I want Google Maps navigation integrated in the same app so I don't switch between tools.
- As a field responder, I want to update my status (on scene, returning) from my device so the operator has live visibility.

### PSAP Admin
- As a PSAP admin, I want a real-time map of all active incidents and unit positions so I can manage resource gaps.
- As a PSAP admin, I want response time trends by region and emergency type so I can identify systemic gaps.
- As a PSAP admin, I want AI classification accuracy logs so I can trust or calibrate the system.

---

## 6. Feature Requirements

### 6.1 Feature: Real-Time Multilingual Triage

**Priority:** P0 — Core
**Description:** The system transcribes the incoming call audio in real time, identifies the language, and classifies the emergency type, severity, caller state, and caller role within 5 seconds of sufficient speech.

**Acceptance Criteria:**
- Emergency classified within 5 seconds of 3+ seconds of intelligible speech
- Supports minimum 8 Indian languages in demo (Hindi, Punjabi, Tamil, Bengali, Marathi, Telugu, Gujarati, Kannada)
- Classification outputs: emergency_type, severity, caller_state, caller_role, confidence_score, key_facts[]
- If confidence < 0.70, operator is flagged with a manual review prompt
- Operator can override any classification field at any time

### 6.2 Feature: One-Tap Dispatch Recommendation

**Priority:** P0 — Core
**Description:** Based on emergency classification, the system queries available units, calculates ETAs via Google Maps, ranks them by composite score, and presents the top 3 to the operator as a dispatch card.

**Acceptance Criteria:**
- Dispatch card appears within 2 seconds of classification
- Shows unit ID, type, hospital affiliation, ETA, and capability match
- One tap confirms dispatch and pushes notification to field responder
- Firebase unit status updates to `dispatched` in real time
- Operator can select non-recommended unit manually

### 6.3 Feature: AI Caller Guidance

**Priority:** P0 — Core
**Description:** In parallel with dispatch, the system generates step-by-step guidance for the caller in their detected language, adapts to their panic level, and delivers it via text-to-speech.

**Acceptance Criteria:**
- Guidance begins generating within 1 second of classification
- Protocols covered: CPR, fire evacuation, wound control, stroke response, stay-calm
- Delivered in detected language using Google Cloud TTS Neural2
- Guidance tone adapts to caller_state (simpler + slower for PANIC_HIGH)
- Operator can pause or override guidance at any time

### 6.4 Feature: Field Responder App

**Priority:** P1 — High
**Description:** Flutter mobile application for field responders receiving dispatch, navigating to scene, and updating incident status.

**Acceptance Criteria:**
- Push notification received within 3 seconds of operator dispatch confirmation
- Notification contains: case type, severity, AI-extracted facts, Google Maps deep link
- In-app status updates: Acknowledged → En Route → On Scene → Returning → Available
- Status updates propagate to operator dashboard in real time

### 6.5 Feature: Admin Analytics Dashboard

**Priority:** P2 — Medium
**Description:** Real-time and historical analytics for PSAP administrators.

**Acceptance Criteria:**
- Live incident heatmap with unit position overlay
- Response time metrics: median, 90th percentile, by region and emergency type
- Unit utilization rates and availability trends
- AI classification accuracy rate (confirmed vs overridden)
- Exportable reports

### 6.6 Feature: Operator Override & Audit Trail

**Priority:** P1 — High
**Description:** Every AI decision can be overridden by the operator. All decisions (AI and operator) are logged.

**Acceptance Criteria:**
- Every AI classification field is editable inline
- Override action is logged with timestamp, field changed, original value, new value
- Audit trail queryable by PSAP admin
- Override data feeds back as negative labels for future model improvement

---

## 7. User Experience Requirements

### 7.1 Operator Dashboard

- Single-screen design — no navigation required during an active call
- AI triage card appears in the upper half, dispatch recommendation in the lower half
- Color coding: RED for Critical, ORANGE for High, YELLOW for Moderate, GREEN for Low
- Caller guidance status visible as a live indicator (not a separate screen)
- Response time: dashboard must reflect new AI output within 500ms of Firebase update

### 7.2 Field Responder App

- Notification must be actionable without opening the app (quick acknowledge)
- Navigation launches in Google Maps or in-app (user preference)
- One-thumb operation — no multi-step flows while driving
- Works on low-end Android devices (minimum Android 8.0, 2GB RAM)

### 7.3 General UX Standards

- All interfaces available in Hindi and English at minimum
- Accessible text sizes (minimum 14sp body)
- Offline-capable for responder (last known dispatch cached locally)
- Dark mode supported (responder use in low-light conditions)

---

## 8. Performance Requirements

| Metric | Target |
|---|---|
| Whisper transcription latency | < 2 seconds per 5-second audio chunk |
| Gemini classification latency | < 3 seconds from transcript receipt |
| Total triage card display time | < 5 seconds from call connect |
| Firebase state propagation | < 200ms across all clients |
| Dispatch card display time | < 2 seconds from classification |
| Push notification delivery | < 3 seconds from operator confirmation |
| Dashboard availability | 99.5% uptime |

---

## 9. Success Metrics

### Hackathon Demo Success
- Live Hindi cardiac arrest call → classification in < 5 seconds ✓
- CPR instructions generated in Hindi and played back ✓
- Dispatch card with ETA displayed ✓
- Field responder notification received ✓
- Judge asks "can this be deployed?" — answer: yes, here's how

### Production KPIs (Post-Hackathon Vision)
- Time-to-dispatch reduction: 8–14 min → < 4 min (target 60% reduction)
- AI triage accuracy: > 85% (measured against operator final decision)
- Caller guidance engagement: > 70% of callers following AI guidance (measured by call duration + outcome)
- Operator cognitive load reduction: measured via NASA-TLX study with actual operators

---

## 10. Constraints

- **Hackathon timeline:** Working prototype in 72 hours
- **No real telephony integration:** Demo uses simulated audio input via browser microphone or pre-recorded clips
- **No real unit data:** Simulated unit positions and availability
- **Google stack required:** All primary services must use Google Cloud / Google APIs
- **Team size:** Small team — architecture must be buildable by 1–2 developers

---

## 11. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Whisper latency too high for live demo | Medium | High | Pre-warm Cloud Run instance; have pre-recorded demo as backup |
| Gemini classification accuracy low on demo audio | Medium | High | Test 20+ Hindi/Punjabi call simulations before demo; tune system prompt |
| Firebase real-time sync delay | Low | Medium | Test on demo network; have local Firebase emulator fallback |
| Language detection wrong on demo | Low | High | Pin demo language to Hindi; show multilingual as a feature slide not live |
| Google Maps API quota exceeded during demo | Low | Medium | Pre-cache demo routes; use Maps JavaScript API with generous quota |

---

*CrisisLink PRD v1.0 — Solution Challenge 2026*
