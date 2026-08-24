import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
model = os.getenv("GEMINI_MODEL", "gemini-3.7-flash").strip()

if not key:
    raise SystemExit("GEMINI_API_KEY is missing from .env.")

url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
payload = {
    "contents": [{
        "role": "user",
        "parts": [{"text": "Reply exactly: GEMINI_AI_ONLINE"}],
    }]
}

print("Testing REAL Google Gemini API")
print("Model:", model)
print("API key: configured (never printed)")
print()

r = requests.post(
    url,
    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    json=payload,
    timeout=(6, 40),
)

if not r.ok:
    try:
        detail = ((r.json().get("error") or {}).get("message")) or r.text
    except Exception:
        detail = r.text
    raise SystemExit(f"Gemini HTTP {r.status_code}: {detail[:800]}")

data = r.json()
parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
text = "\n".join(p.get("text", "") for p in parts if not p.get("thought")).strip()

print("Gemini response:", text)
if "GEMINI_AI_ONLINE" in text.upper():
    print("\nPASS — REAL GEMINI AI IS ONLINE")
else:
    print("\nGemini answered, so the connection is online.")
