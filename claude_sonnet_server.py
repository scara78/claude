"""
Claude Sonnet Overchat.ai API Server
Deploy to Render for production use
Based on claude-sonnet-3-5.py script
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import uuid
import time
import json
import os

app = Flask(__name__)
CORS(app)

# -----------------------------------------------------------------------
# Configuration — mirrors claude-sonnet-3-5.py exactly
# -----------------------------------------------------------------------
BASE_URL = "https://api.overchat.ai/v1/chat/completions"
MODEL    = "anthropic/claude-opus-4-6"        # or claude-haiku-4-5-20251001
PERSONA_ID  = "claude-opus-4-6-landing"
MAX_TOKENS  = 4000
TEMPERATURE = 0.5

# -----------------------------------------------------------------------
# Build a fresh requests.Session with browser-like headers (same as script)
# -----------------------------------------------------------------------
def make_session(device_uuid: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "accept":            "*/*",
        "content-type":      "application/json",
        "x-device-platform": "web",
        "x-device-version":  "1.0.44",
        "x-device-language": "en-US",
        "x-device-uuid":     device_uuid,
        "origin":  "https://overchat.ai",
        "referer": "https://overchat.ai/",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    })
    return s


# -----------------------------------------------------------------------
# Core function — same SSE-parsing logic as claude-sonnet-3-5.py
# -----------------------------------------------------------------------
def send_message(user_message: str, chat_id: str | None = None):
    if chat_id is None:
        chat_id = str(uuid.uuid4())

    # Fresh UUID per request (guest mode, same as the working local script)
    device_uuid = str(uuid.uuid4())
    sess = make_session(device_uuid)

    messages = [
        {"id": str(uuid.uuid4()), "role": "user",   "content": user_message},
        {"id": str(uuid.uuid4()), "role": "system", "content": ""},
    ]

    payload = {
        "chatId":            chat_id,
        "model":             MODEL,
        "messages":          messages,
        "personaId":         PERSONA_ID,
        "stream":            True,
        "temperature":       TEMPERATURE,
        "max_tokens":        MAX_TOKENS,
        "frequency_penalty": 0,
        "presence_penalty":  0,
        "top_p":             0.95,
    }

    # ---------------------------------------------------------------
    # Critical fix: use a generous timeout.
    # connect=10s, read=120s — overchat can be slow on free tier.
    # ---------------------------------------------------------------
    response = sess.post(BASE_URL, json=payload, stream=True, timeout=(10, 120))

    if response.status_code not in (200, 201):
        error_body = response.text[:500]
        return None, None, response.status_code, error_body

    # Parse SSE stream — identical to the local script
    full_reply = []
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data:"):
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                event = json.loads(data)
                delta = (
                    event.get("choices", [{}])[0]
                         .get("delta", {})
                         .get("content", "")
                )
                if delta:
                    delta = delta.encode("utf-8", errors="ignore").decode("utf-8")
                    full_reply.append(delta)
            except json.JSONDecodeError:
                pass

    return chat_id, "".join(full_reply), 200, None


# -----------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    """API documentation / landing page"""
    base = request.host_url.rstrip("/")
    return jsonify({
        "name":    "Claude Overchat API Server",
        "version": "1.1",
        "model":   MODEL,
        "endpoints": {
            "POST /chat": {
                "description": "Send a message and get a reply",
                "body":    {"message": "your text here", "chat_id": "(optional)"},
                "example": f"curl -X POST {base}/chat -H 'Content-Type: application/json' -d '{{\"message\": \"Hello\"}}'",
            },
            "GET /health": "Health check",
        },
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({"status": "healthy", "model": MODEL})


@app.route("/chat", methods=["POST"])
@app.route("/v1/chat/completions", methods=["POST"])
def chat():
    """
    Main chat endpoint.
    Body: { "message": "...", "chat_id": "(optional uuid to continue a conversation)" }
    """
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "Missing 'message' in JSON body"}), 400

    user_message = data["message"].strip()
    if not user_message:
        return jsonify({"error": "'message' must not be empty"}), 400

    chat_id = data.get("chat_id") or None   # let it be None → auto-generated

    start = time.time()
    try:
        chat_id, reply, status, err = send_message(user_message, chat_id)
    except requests.exceptions.Timeout:
        return jsonify({
            "error":   "Request to overchat.ai timed out",
            "tip":     "overchat.ai may be slow or rate-limiting this IP. Try again."
        }), 504
    except Exception as exc:
        return jsonify({"error": "Internal error", "detail": str(exc)}), 500

    elapsed = time.time() - start

    if status not in (200, 201):
        return jsonify({
            "error":   f"overchat.ai returned HTTP {status}",
            "details": err,
        }), 502

    if not reply:
        return jsonify({
            "error": "Empty reply from overchat.ai",
            "tip":   "The API returned a stream but no content was found. "
                     "The model or persona ID may have changed."
        }), 502

    return jsonify({
        "success":       True,
        "model":         MODEL,
        "message":       reply,
        "chat_id":       chat_id,
        "response_time": f"{elapsed:.2f}s",
    })


# -----------------------------------------------------------------------
# Entry point (dev only — Render uses gunicorn)
# -----------------------------------------------------------------------
if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "production") != "production"
    print(f"\n🚀 Starting server on port {port} (debug={debug})")
    app.run(host="0.0.0.0", port=port, debug=debug)
