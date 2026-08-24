import os
import threading
import time
import json
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv

from red_shed_crawler import (
    get_state,
    load_index,
    install_bootstrap_if_needed,
    retrieve,
    run_background_refresh,
)

load_dotenv()

ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=str(ROOT), static_url_path="")

GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash").strip()
GEMINI_REST_BASE = os.getenv("GEMINI_REST_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
GEMINI_CONNECT_TIMEOUT = max(3, int(os.getenv("GEMINI_CONNECT_TIMEOUT", "6")))
GEMINI_READ_TIMEOUT = max(15, int(os.getenv("GEMINI_READ_TIMEOUT", "40")))
GEMINI_MODEL_CANDIDATES = []
for _model in [GEMINI_MODEL, "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"]:
    if _model and _model not in GEMINI_MODEL_CANDIDATES:
        GEMINI_MODEL_CANDIDATES.append(_model)


# V7 refreshes Red Shed website knowledge regularly while the server is running.
AUTO_REFRESH_MINUTES = max(5, int(os.getenv("REDSHED_AUTO_REFRESH_MINUTES", "15")))
AUTO_REFRESH_SECONDS = AUTO_REFRESH_MINUTES * 60
FAILED_REFRESH_RETRY_SECONDS = max(120, int(os.getenv("REDSHED_FAILED_REFRESH_RETRY_SECONDS", "600")))

SYSTEM_GUIDE = """
You are the Red Shed AI Concierge for the "Is Rowing For Me?" microsite in Canberra, Australia.

MISSION
Welcome prospective rowers, reduce hesitation, answer practical questions directly, and guide people
toward the most useful self-service Red Shed next step. The aim is to reduce unnecessary staff email
back-and-forth and help a person move from curiosity toward trying rowing.

RAG / SOURCE-OF-TRUTH RULE
For ANY Red Shed-specific fact, reason from the RED SHED WEBSITE EXCERPTS retrieved for this turn. These excerpts come from the live Red Shed crawler when available, with a bundled official-site snapshot only as startup coverage.
The crawler is designed to index public, discoverable Red Shed pages, microsite-style pages, subdomains,
and PDFs from allowed official Red Shed sites.

Do not answer Red Shed-specific questions from memory. Use the retrieved official excerpts, synthesize them naturally, and never copy an excerpt mechanically when a clearer answer can be generated.

ANTI-DEFLECTION RULE
For normal questions that the official website already answers:
- answer the question directly;
- do not simply tell the person to email or contact Red Shed;
- give the most relevant self-service next step or official page.

Only suggest contacting Red Shed when:
- the official source specifically requires staff involvement;
- the question genuinely cannot be resolved from the current public material; or
- it concerns a personal/special situation requiring human judgement.

PSYCHOLOGICAL BARRIERS
Be warm and non-judgmental about concerns such as age, fitness, swimming/water confidence,
being a complete beginner, feeling rusty, schedule fit, or fear of being the least capable person.
Do not make up reassurance that conflicts with Red Shed's current published requirements.

DO NOT INVENT
Never invent:
- course dates or start dates
- remaining places
- live availability
- prices or pass inclusions
- membership conditions
- swimming/safety requirements
- medical requirements
- staff names
- booking status
- whether a returning rower can definitely skip a program
- timetable slots
- policies

If those facts are present in the current retrieved Red Shed material, you may state them accurately.

GENERAL ROWING KNOWLEDGE
You may answer simple general rowing questions if useful, but clearly distinguish general knowledge from
Red Shed-specific information.

ANSWER STYLE
- Plain English.
- Friendly and practical.
- Usually 50-110 words.
- Maximum 3-4 short paragraphs or bullets unless the user asks for detail.
- Answer first; explanation second.
- Finish with ONE clear next step when useful.
- Avoid jargon and large walls of text.
- Use plain text with short bullets when useful. Do not output raw Markdown headings or decorative asterisks.
- Bold markup is optional; if used, only use **bold** for very short labels.
- Do not write fake/simulated booking links. The website UI provides official source links separately.
"""


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def index_age_seconds(index):
    dt = parse_iso(index.get("generated_at"))
    if not dt:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return max(0, (datetime.now(timezone.utc) - dt).total_seconds())


def ensure_fresh_index():
    index = install_bootstrap_if_needed()
    age = index_age_seconds(index)
    state = get_state()

    stale = (
        not index.get("count")
        or index.get("source_mode") != "live_website"
        or age is None
        or age >= AUTO_REFRESH_SECONDS
    )

    # If a live refresh just failed, keep serving the last-good local knowledge
    # instead of immediately launching the crawler again and again.
    recent_failed_attempt = False
    if state.get("error") and state.get("finished_at"):
        finished = parse_iso(state.get("finished_at"))
        if finished:
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=timezone.utc)
            seconds_since_failure = max(
                0,
                (datetime.now(timezone.utc) - finished).total_seconds(),
            )
            recent_failed_attempt = seconds_since_failure < FAILED_REFRESH_RETRY_SECONDS

    if stale and not state.get("indexing") and not recent_failed_attempt:
        run_background_refresh()

    return index


def auto_refresh_loop():
    while True:
        try:
            ensure_fresh_index()
        except Exception as exc:
            print("Automatic Red Shed knowledge refresh check failed:", repr(exc))
        time.sleep(60)



def source_cards(matches):
    cards = []
    seen = set()
    for match in matches:
        url = match.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        cards.append({
            "title": match.get("title") or url,
            "url": url,
            "host": match.get("host") or "redshed.org.au",
        })
    return cards[:5]



AI_STATE_LOCK = threading.Lock()
AI_STATE = {
    "status": "not_checked",       # not_checked | online | offline
    "last_success_at": None,
    "last_error": None,
    "last_model": None,
    "last_transport": None,
}


def set_ai_state(**updates):
    with AI_STATE_LOCK:
        AI_STATE.update(updates)


def get_ai_state():
    with AI_STATE_LOCK:
        return dict(AI_STATE)


def redact_secret(text):
    text = str(text or "")
    if GEMINI_API_KEY:
        text = text.replace(GEMINI_API_KEY, "[REDACTED]")
    return text[:900]


def parse_gemini_rest_text(data):
    """Extract only final answer text from a Gemini GenerateContent response."""
    candidates = data.get("candidates") or []
    if not candidates:
        prompt_feedback = data.get("promptFeedback") or {}
        reason = prompt_feedback.get("blockReason")
        if reason:
            raise RuntimeError(f"Gemini blocked the prompt: {reason}")
        raise RuntimeError("Gemini returned no candidates.")

    parts = ((candidates[0].get("content") or {}).get("parts") or [])
    final_parts = []
    for part in parts:
        # Ignore explicit thought/reasoning parts if the API returns them.
        if part.get("thought") is True:
            continue
        text = part.get("text")
        if text:
            final_parts.append(text)

    answer = "\n".join(final_parts).strip()
    if not answer:
        raise RuntimeError("Gemini returned no final text.")
    return answer


def gemini_rest_generate(interaction_input, model):
    """Call Gemini directly through Google's documented GenerateContent REST endpoint."""
    import requests

    url = f"{GEMINI_REST_BASE}/models/{model}:generateContent"
    payload = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_GUIDE}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": interaction_input}],
            }
        ],
    }

    response = requests.post(
        url,
        headers={
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=(GEMINI_CONNECT_TIMEOUT, GEMINI_READ_TIMEOUT),
    )

    if not response.ok:
        detail = ""
        try:
            err = response.json()
            detail = (
                ((err.get("error") or {}).get("message"))
                or json.dumps(err)[:500]
            )
        except Exception:
            detail = response.text[:500]

        exc = RuntimeError(f"Gemini HTTP {response.status_code}: {detail}")
        setattr(exc, "status_code", response.status_code)
        raise exc

    return parse_gemini_rest_text(response.json())


def gemini_sdk_generate(interaction_input, model):
    """SDK fallback in case the REST transport itself has a local compatibility issue."""
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=GEMINI_READ_TIMEOUT * 1000),
    )

    response = client.models.generate_content(
        model=model,
        contents=interaction_input,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_GUIDE,
        ),
    )
    answer = (getattr(response, "text", "") or "").strip()
    if not answer:
        raise RuntimeError("Gemini SDK returned no final text.")
    return answer


def call_gemini_ai(interaction_input):
    """
    REAL AI path.
    1. Gemini GenerateContent REST call (minimal documented schema).
    2. Retry once for transient service/rate failures.
    3. Try compatible Flash model IDs if a model endpoint is unavailable.
    4. SDK fallback only if REST transport/schema fails.
    Never silently replace the answer with hard-coded text.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "Gemini API key is not configured. Add GEMINI_API_KEY to .env and restart the server."
        )

    errors = []

    for model in GEMINI_MODEL_CANDIDATES:
        for attempt in range(2):
            try:
                answer = gemini_rest_generate(interaction_input, model)
                set_ai_state(
                    status="online",
                    last_success_at=datetime.now(timezone.utc).isoformat(),
                    last_error=None,
                    last_model=model,
                    last_transport="Gemini REST GenerateContent",
                )
                return answer, model, "Gemini REST GenerateContent"
            except Exception as exc:
                msg = redact_secret(exc)
                status_code = getattr(exc, "status_code", None)
                errors.append(f"{model} REST: {msg}")

                transient = status_code in (429, 500, 502, 503, 504)
                model_problem = status_code in (400, 404)

                if transient and attempt == 0:
                    time.sleep(1.6)
                    continue

                # A 400/404 can be model-specific, so try the next model.
                if model_problem:
                    break

                # 401/403/key/project errors should not waste calls on every model.
                if status_code in (401, 403):
                    set_ai_state(
                        status="offline",
                        last_error=msg,
                        last_model=model,
                        last_transport="Gemini REST GenerateContent",
                    )
                    raise RuntimeError(msg)

                break

    # Transport fallback: same Gemini AI, different Python client path.
    for model in GEMINI_MODEL_CANDIDATES[:2]:
        try:
            answer = gemini_sdk_generate(interaction_input, model)
            set_ai_state(
                status="online",
                last_success_at=datetime.now(timezone.utc).isoformat(),
                last_error=None,
                last_model=model,
                last_transport="Google Gen AI SDK",
            )
            return answer, model, "Google Gen AI SDK"
        except Exception as exc:
            errors.append(f"{model} SDK: {redact_secret(exc)}")

    final_error = " | ".join(errors[-4:]) or "Gemini did not return an answer."
    set_ai_state(
        status="offline",
        last_error=final_error,
        last_model=None,
        last_transport=None,
    )
    raise RuntimeError(final_error)


def run_ai_health_check():
    """Small real Gemini request used by the status badge and demo checker."""
    if not GEMINI_API_KEY:
        set_ai_state(
            status="offline",
            last_error="GEMINI_API_KEY is not configured.",
            last_model=None,
            last_transport=None,
        )
        return

    probe = (
        "This is a connection test. Reply with exactly: GEMINI_AI_ONLINE"
    )
    try:
        answer, model, transport = call_gemini_ai(probe)
        if "GEMINI_AI_ONLINE" not in answer.upper():
            # It still proved that Gemini answered successfully.
            set_ai_state(
                status="online",
                last_success_at=datetime.now(timezone.utc).isoformat(),
                last_error=None,
                last_model=model,
                last_transport=transport,
            )
    except Exception as exc:
        set_ai_state(
            status="offline",
            last_error=redact_secret(exc),
        )


@app.get("/api/status")
def status():
    index = ensure_fresh_index()
    state = get_state()
    ai_state = get_ai_state()
    age = index_age_seconds(index)

    return jsonify({
        "version": "7.7",
        "ai_provider": "Google Gemini",
        "ai_key_configured": bool(GEMINI_API_KEY),
        "ai_status": ai_state.get("status"),
        "ai_online": ai_state.get("status") == "online",
        "ai_last_success_at": ai_state.get("last_success_at"),
        "ai_last_error": ai_state.get("last_error"),
        "ai_model": ai_state.get("last_model") or GEMINI_MODEL,
        "ai_transport": ai_state.get("last_transport"),
        "chat_ready": bool(index.get("count", 0)) and bool(GEMINI_API_KEY),
        "index_ready": bool(index.get("count", 0)),
        "knowledge_mode": index.get("source_mode", "unknown"),
        "knowledge_snapshot_at": index.get("snapshot_at"),
        "indexed_pages": int(index.get("count", 0)),
        "indexed_hosts": index.get("hosts", []),
        "indexed_host_count": len(index.get("hosts", [])),
        "site_roots": index.get("site_roots", []),
        "index_generated_at": index.get("generated_at"),
        "index_age_seconds": int(age) if age is not None else None,
        "indexing": bool(state.get("indexing")),
        "index_error": state.get("error"),
        "current_url": state.get("current_url"),
        "auto_refresh_minutes": AUTO_REFRESH_MINUTES,
        "failed_refresh_retry_seconds": FAILED_REFRESH_RETRY_SECONDS,
    })


@app.post("/api/ai-check")
def ai_check():
    if not GEMINI_API_KEY:
        return jsonify({
            "ok": False,
            "error": "GEMINI_API_KEY is not configured in .env.",
        }), 503

    run_ai_health_check()
    state = get_ai_state()

    if state.get("status") == "online":
        return jsonify({
            "ok": True,
            "provider": "Google Gemini",
            "model": state.get("last_model"),
            "transport": state.get("last_transport"),
        })

    return jsonify({
        "ok": False,
        "error": state.get("last_error") or "Gemini health check failed.",
    }), 503


@app.get("/api/knowledge")
def knowledge():
    index = load_index()

    # Expose safe metadata only, not secrets.
    pages = [
        {
            "title": page.get("title"),
            "url": page.get("url"),
            "host": page.get("host"),
            "kind": page.get("kind"),
            "fetched_at": page.get("fetched_at"),
        }
        for page in index.get("pages", [])
    ]

    return jsonify({
        "generated_at": index.get("generated_at"),
        "count": index.get("count", 0),
        "hosts": index.get("hosts", []),
        "site_roots": index.get("site_roots", []),
        "pages": pages,
    })


@app.post("/api/refresh")
def refresh():
    started = run_background_refresh()

    if not started:
        return jsonify({"error": "A Red Shed website refresh is already running."}), 409

    return jsonify({"started": True})


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    history = payload.get("history", [])

    if not message:
        return jsonify({"error": "Message is required."}), 400

    if not GEMINI_API_KEY:
        return jsonify({
            "error": (
                "Gemini AI is not configured. Open CONFIGURE_GEMINI.command, "
                "save a fresh GEMINI_API_KEY in .env, then restart START_V7_7.command."
            )
        }), 503

    index = ensure_fresh_index()
    if not index.get("count"):
        return jsonify({
            "error": "No Red Shed website knowledge is available yet."
        }), 503

    # RAG retrieval: retrieve the Red Shed website excerpts most relevant to THIS question.
    matches = retrieve(message, k=12)

    blocks = []
    for i, match in enumerate(matches, 1):
        blocks.append(
            f"[RED SHED WEBSITE SOURCE {i}]\n"
            f"TITLE: {match['title']}\n"
            f"URL: {match['url']}\n"
            f"HOST: {match.get('host', 'redshed.org.au')}\n"
            f"CONTENT:\n{match['chunk']}"
        )

    context = "\n\n".join(blocks) if blocks else (
        "No strong Red Shed excerpt matched this question. "
        "For Red Shed-specific facts, say that the current indexed website material does not confirm the answer."
    )

    recent = []
    if isinstance(history, list):
        for item in history[-8:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "user")).upper()
            content = str(item.get("content", ""))[:1500]
            if content:
                recent.append(f"{role}: {content}")

    interaction_input = f"""
You are answering inside the Red Shed 'Is Rowing For Me?' microsite.

RECENT CONVERSATION
{chr(10).join(recent) if recent else "(none)"}

RETRIEVED OFFICIAL RED SHED WEBSITE EXCERPTS
{context}

VISITOR'S QUESTION
{message}

TASK
Generate a fresh, conversational answer to the visitor.
Use the retrieved Red Shed excerpts as the factual grounding for all Red Shed-specific claims.
Do not just paste or mechanically summarize the excerpts.
Resolve the visitor's real question, explain the most useful next step, and keep the answer concise.
If a changing fact is not in the excerpts, say that clearly instead of guessing.
"""

    try:
        answer, model_used, transport = call_gemini_ai(interaction_input)
    except Exception as exc:
        safe = redact_secret(exc)
        print("Gemini RAG request failed:", safe)
        return jsonify({
            "error": (
                "Gemini AI could not answer this request. "
                "The Red Shed knowledge is available, but the Google Gemini connection failed. "
                f"Details: {safe}"
            ),
            "provider": "Google Gemini",
        }), 503

    sources = source_cards(matches)

    return jsonify({
        "answer": answer,
        "sources": sources,
        "provider": "Google Gemini",
        "model": model_used,
        "transport": transport,
        "grounding_mode": index.get("source_mode", "unknown"),
        "grounding_count": len(matches),
        "knowledge_generated_at": index.get("generated_at"),
        "degraded": False,
    })


@app.get("/api/diagnostics")
def diagnostics():
    """Safe diagnostics. Never returns the API key."""
    try:
        import importlib.metadata as metadata
        sdk_version = metadata.version("google-genai")
    except Exception:
        sdk_version = "unknown"

    index = load_index()
    ai_state = get_ai_state()

    return jsonify({
        "version": "7.7",
        "provider": "Google Gemini RAG",
        "key_configured": bool(GEMINI_API_KEY),
        "ai_status": ai_state.get("status"),
        "ai_model": ai_state.get("last_model") or GEMINI_MODEL,
        "ai_transport": ai_state.get("last_transport"),
        "ai_last_error": ai_state.get("last_error"),
        "knowledge_mode": index.get("source_mode", "unknown"),
        "indexed_pages": int(index.get("count", 0)),
        "indexed_hosts": index.get("hosts", []),
        "google_genai_version": sdk_version,
        "port": int(os.getenv("PORT", "8007")),
    })


@app.get("/")
def home():
    return send_from_directory(ROOT, "index.html")


@app.get("/<path:path>")
def files(path):
    return send_from_directory(ROOT, path)


if __name__ == "__main__":
    existing = install_bootstrap_if_needed()
    age = index_age_seconds(existing)

    if not existing.get("count"):
        print("WARNING: No bundled Red Shed knowledge could be loaded.")
        run_background_refresh()
    elif existing.get("source_mode") != "live_website":
        print(
            f"Loaded bundled Red Shed knowledge immediately: {existing['count']} items. "
            "Refreshing the live website in the background…"
        )
        run_background_refresh()
    elif age is None or age >= AUTO_REFRESH_SECONDS:
        print("Red Shed knowledge is stale. Refreshing in the background…")
        run_background_refresh()
    else:
        print(
            f"Loaded Red Shed knowledge: {existing['count']} pages/documents "
            f"across {len(existing.get('hosts', []))} host(s)"
        )

    threading.Thread(target=auto_refresh_loop, daemon=True).start()
    threading.Thread(target=run_ai_health_check, daemon=True).start()

    print("\nIS ROWING FOR ME? — RED SHED MVP V7.7")
    PORT = int(os.getenv("PORT", "8007"))
    print(f"Open: http://127.0.0.1:{PORT}")
    print(f"Knowledge refresh window: {AUTO_REFRESH_MINUTES} minutes")
    print(
        f"AI: Google Gemini RAG · preferred model {GEMINI_MODEL}"
        if GEMINI_API_KEY
        else "AI: Gemini API key NOT configured — chatbot will not pretend to be AI"
    )
    print("Primary source of truth: https://redshed.org.au/\n")

    PORT = int(os.getenv("PORT", "8007"))
    app.run(host="127.0.0.1", port=PORT, debug=False)
