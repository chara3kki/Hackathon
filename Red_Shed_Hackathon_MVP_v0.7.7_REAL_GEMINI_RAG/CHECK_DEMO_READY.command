#!/bin/bash
cd "$(dirname "$0")"

echo ""
echo "V7.7 REAL GEMINI RAG — DEMO CHECK"
echo "=================================="
echo ""

python3 - <<'PY'
import json, urllib.request

base="http://127.0.0.1:8007"

def get(path):
    with urllib.request.urlopen(base+path, timeout=8) as r:
        return json.load(r)

try:
    s=get("/api/status")
    print("Server: READY")
    print("Version:", s.get("version"))
    print("Red Shed knowledge items:", s.get("indexed_pages"))
    print("Knowledge mode:", s.get("knowledge_mode"))
    print("Gemini key configured:", s.get("ai_key_configured"))
    print("Gemini status:", s.get("ai_status"))
except Exception as e:
    print("SERVER CHECK FAILED:", repr(e))
    print("Run START_V7_7.command first.")
    raise SystemExit(1)

print("\nRunning a real Gemini health check...")
req=urllib.request.Request(base+"/api/ai-check", data=b"{}", headers={"Content-Type":"application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=55) as r:
        d=json.load(r)
    print("Gemini AI: ONLINE")
    print("Model:", d.get("model"))
    print("Transport:", d.get("transport"))
except Exception as e:
    print("GEMINI AI CHECK FAILED:", repr(e))
    raise SystemExit(1)

print("\nTesting the full Red Shed RAG chatbot...")
payload=json.dumps({
    "message":"I have never rowed before and I am not very fit. Where should I start?",
    "history":[]
}).encode()

req=urllib.request.Request(
    base+"/api/chat",
    data=payload,
    headers={"Content-Type":"application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=55) as r:
        d=json.load(r)
    print("RAG CHAT: PASS")
    print("Provider:", d.get("provider"))
    print("Model:", d.get("model"))
    print("Grounding mode:", d.get("grounding_mode"))
    print("Retrieved excerpts:", d.get("grounding_count"))
    print("Answer preview:", (d.get("answer") or "")[:300])
    print("\nREADY FOR DEMO — THE CHATBOT IS USING GEMINI AI + RED SHED WEBSITE KNOWLEDGE")
except Exception as e:
    print("RAG CHAT FAILED:", repr(e))
    raise SystemExit(1)
PY

echo ""
read -p "Press Enter to close..."
