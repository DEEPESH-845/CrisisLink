# CrisisLink
## AI Co-Pilot for India's 112 Emergency Response Infrastructure

**Track:** Rapid Crisis Response — Open Innovation
**Stack:** Whisper / Gemini Live · Firebase · Google Maps · Flutter · Cloud Run · Vertex AI

---

## The Problem Nobody Is Talking About

India's 112 emergency number receives **700,000 calls every single day.**

Operators are overwhelmed, undertrained, and working with zero AI assistance. The average time from call to dispatch is **8–14 minutes.** In cardiac arrest, brain death begins at **6 minutes.** In a fire, a building fills with lethal smoke in **4 minutes.**

The gap between a call and a response is not a logistics problem. It is an **intelligence problem.** And nobody has built the AI layer to close it.

> *"Every minute a 112 operator spends manually identifying the emergency, finding an available unit, and locating the caller is a minute the victim doesn't have."*

---

## The Real Bottleneck

When a panicked caller dials 112 today, a human operator must simultaneously:

- Understand the emergency (often through broken speech, panic, regional dialect)
- Determine severity and priority
- Manually look up nearest available units
- Contact dispatch separately
- Keep the caller calm and on the line

All of this happens serially. All of it takes time. None of it is assisted by AI.

**CrisisLink collapses this entire sequence into 5 seconds — in any Indian language.**

---

## What CrisisLink Does

The moment a call connects, CrisisLink's AI engine executes four actions **simultaneously:**

### 1. Multilingual Call Triage
**Whisper (OpenAI) + Gemini Live** transcribes and understands the call in real-time across all 22 scheduled Indian languages — Hindi, Punjabi, Tamil, Bengali, Marathi, Telugu and more. No manual language switching. No missed context from dialect. Emergency type (medical / fire / crime / accident / disaster) and severity score are generated in under 5 seconds.

### 2. Caller State Intelligence
Beyond words, CrisisLink detects **panic level, speech coherence, and whether the caller is the victim or a bystander.** A panicked child gets simpler, slower instructions. A calm bystander gets precise clinical guidance. The system adapts — the operator doesn't have to.

### 3. Instant Dispatch Recommendation
Firebase Realtime DB holds live unit availability across ambulances, fire brigades, and police. Google Maps Platform calculates traffic-aware ETA for every nearby unit. The operator sees a ranked dispatch card — **one tap confirms and sends.** No phone calls to find an available unit. No manual map lookup.

### 4. AI-Guided Caller Support
While dispatch is happening, **Gemini generates real-time guidance for the caller** — CPR instructions, fire evacuation steps, wound control, or calm-down protocols — delivered in their own language, at their comprehension level. This runs in parallel with dispatch, not after it. The caller is being helped the moment the AI understands the situation.

---

## The Demo That Wins

A teammate calls the live CrisisLink system speaking Hindi:

> *"Mere papa gir gaye, unhe saans nahi aa rahi"*
> *(My father fell, he can't breathe)*

In 4 seconds, the operator dashboard shows:

```
EMERGENCY TYPE:  Cardiac — Critical
CALLER STATE:    High panic / Female / Bystander
NEAREST UNIT:    Ambulance 7 — PGIMER Chandigarh — ETA 6 min
DISPATCH:        [ONE TAP TO CONFIRM]
CALLER GUIDANCE: Generating Hindi CPR instructions...
```

Gemini simultaneously speaks to the caller:
> *"Unhe seedha letao, haath seene ke beech rakho, zyada zyada dabaao..."*

The judge watches a life being saved in real time. That is the moment.

---

## Three Users. One App.

| Role | What They See |
|---|---|
| **112 Operator** | Live triage card, severity score, one-tap dispatch, Gemini caller summary |
| **Field Responder** | Google Maps route, case type, patient context, live status updates |
| **PSAP Admin** | Incident heatmap, unit availability, Vertex AI response time analytics |

All three roles powered by a single **Flutter** codebase — web dashboard for operators, mobile app for responders.

---

## Why This Wins

**Scale is already there.** 700,000 daily callers didn't need to be acquired. They already exist. CrisisLink is infrastructure, not a product looking for users.

**Google stack is native.** Gemini Live for intelligence. Firebase for real-time state. Google Maps for routing. Flutter for cross-platform. Vertex AI for analytics. Every Google technology earns its place — nothing is forced.

**Multilingual is the differentiator.** No team in this hackathon will demo a live Hindi cardiac arrest call with AI-generated CPR instructions. That moment belongs to CrisisLink.

**It's not a new app. It's the missing intelligence layer** on top of infrastructure India already depends on.

---

## Impact at Scale

- Response time reduction target: **8–14 min → under 4 min** for first AI-assisted triage
- Caller survival guidance: active for **100% of calls** during dispatch window
- Language coverage: **22+ Indian languages** from day one, no additional training
- Operator cognitive load: reduced from 6 parallel tasks to **1 confirmation tap**

---

*Built for the Solution Challenge 2026 — Google Developers × Hack2Skill*
*Team: Prabinder Singh, Thapar Institute of Engineering & Technology*
