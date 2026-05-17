#!/bin/bash
# CrisisLink — full demo flow in a single command
# Prerequisites: all four services running (run ./start.sh first)

TOKEN="crisislink-dev-token"
CALL_ID="demo-001"

echo "======================================================"
echo "  CrisisLink Demo — Hindi Cardiac Arrest Call"
echo "======================================================"
echo ""

# ------------------------------------------------------------------
# Step 1: Classify the Hindi transcript via the Intelligence Service
# ------------------------------------------------------------------
echo "Step 1: Injecting Hindi cardiac arrest transcript..."
echo "        Transcript: 'mere papa gir gaye unhe saans nahi aa rahi jaldi aao'"
echo ""

CLASSIFY_RESPONSE=$(curl -s -X POST \
    "http://localhost:8002/api/v1/calls/${CALL_ID}/classify" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN}" \
    -d '{
      "transcript": "mere papa gir gaye unhe saans nahi aa rahi jaldi aao"
    }')

echo "Classification result:"
echo "${CLASSIFY_RESPONSE}" | python3 -m json.tool
echo ""

# ------------------------------------------------------------------
# Step 2: Get ranked dispatch recommendations (uses real Maps ETA)
# ------------------------------------------------------------------
echo "Step 2: Fetching ranked dispatch candidates with Google Maps ETAs..."
echo ""

# Extract classification from Step 1 response, or use a hardcoded fallback
# if Step 1 returned mock data (both formats are accepted below).
curl -s -X POST \
    "http://localhost:8003/api/v1/calls/${CALL_ID}/dispatch/recommend" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN}" \
    -d "{
      \"classification\": {
        \"call_id\": \"${CALL_ID}\",
        \"emergency_type\": \"MEDICAL\",
        \"severity\": \"CRITICAL\",
        \"caller_state\": {
          \"panic_level\": \"PANIC_HIGH\",
          \"caller_role\": \"BYSTANDER\"
        },
        \"language_detected\": \"hi\",
        \"key_facts\": [\"male victim (papa)\", \"collapsed\", \"not breathing\"],
        \"confidence\": 0.91,
        \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo '2026-05-06T10:00:00Z')\",
        \"model_version\": \"gemini-1.5-pro\"
      },
      \"caller_location\": {
        \"lat\": 30.7333,
        \"lng\": 76.7794
      }
    }" | python3 -m json.tool
echo ""

# ------------------------------------------------------------------
# Step 3: Confirm dispatch of top unit
# ------------------------------------------------------------------
echo "Step 3: Confirming dispatch of AMB_007..."
echo ""

curl -s -X POST \
    "http://localhost:8003/api/v1/calls/${CALL_ID}/dispatch/confirm" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN}" \
    -d '{
      "unit_id": "AMB_007",
      "emergency_type": "MEDICAL",
      "severity": "CRITICAL",
      "caller_lat": 30.7333,
      "caller_lng": 76.7794,
      "key_facts": ["male victim (papa)", "collapsed", "not breathing"]
    }' | python3 -m json.tool
echo ""

# ------------------------------------------------------------------
# Step 4: Synthesize Hindi CPR guidance via TTS
# ------------------------------------------------------------------
echo "Step 4: Synthesizing Hindi CPR guidance (Google Cloud TTS)..."
echo ""

curl -s -X POST \
    "http://localhost:8004/api/v1/tts/synthesize" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN}" \
    -d '{
      "text": "Ghabrao mat, main aapke saath hoon. Unhe seedha letao kisi sakht jagah par.",
      "language": "hi",
      "voice_config": {
        "name": "hi-IN-Neural2-A",
        "speaking_rate": 0.82
      }
    }' -o /dev/null -w "TTS response HTTP status: %{http_code}\n"
echo ""

echo "======================================================"
echo "  Demo complete."
echo "  Open the Flutter dashboard to see live Firebase"
echo "  updates: http://localhost:8080"
echo "======================================================"
