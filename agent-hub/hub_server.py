"""Agent Hub — single landing page listing every local agent's status.

Convention: each agent writes its own data/status.json:
    {"name": "...", "status": "running|idle|offline", "last_action": "...", "timestamp": "...", "url": "http://localhost:PORT"}
Hub never talks to an agent directly — it only reads these files, so a dead
or unmodified agent just shows as "no status file yet" instead of crashing the hub.
"""
import json
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

ROOT = Path(__file__).resolve().parent.parent

AGENTS = [
    {
        "key": "jimmy",
        "label": "ג'ימי (מסחר)",
        "status_file": ROOT / "ninjatrader-mcp" / "data" / "status.json",
        "url": "http://localhost:5000",
        "chat_url": "http://localhost:5000/api/chat",
    },
    {
        "key": "max",
        "label": "מקס (הזדמנויות עסקיות)",
        "status_file": ROOT / "business-scout" / "data" / "status.json",
        "url": "http://localhost:5001",
        "chat_url": "http://localhost:5001/api/chat",
    },
]


def load_status(agent):
    f = agent["status_file"]
    if not f.exists():
        return {"status": "no status file yet", "last_action": "-", "timestamp": "-"}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"status": "error reading status", "last_action": "-", "timestamp": "-"}


@app.route("/")
def index():
    cards = []
    for agent in AGENTS:
        info = load_status(agent)
        cards.append({**agent, **info})
    return render_template("index.html", cards=cards)


@app.route("/meeting")
def meeting():
    return render_template("meeting.html", agents=AGENTS)


@app.route("/api/meeting", methods=["POST"])
def api_meeting():
    """Round-table: each agent answers in turn, seeing what previous agents said."""
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "no message"}), 400

    transcript = []
    prior_context = ""
    for agent in AGENTS:
        if prior_context:
            full_msg = (
                f"[ישיבת צוות] שאלה מהיזם: {message}\n\n"
                f"מה שנאמר עד כה בישיבה:\n{prior_context}\n\n"
                f"הגב לשאלה מנקודת המבט שלך. אם רלוונטי, התייחס למה שנאמר."
            )
        else:
            full_msg = f"[ישיבת צוות] שאלה מהיזם: {message}\n\nהגב מנקודת המבט שלך."

        try:
            r = requests.post(agent["chat_url"], json={"message": full_msg}, timeout=60)
            reply = r.json().get("reply", "(אין תשובה)")
        except Exception as e:
            reply = f"({agent['label']} לא מגיב כרגע — הדשבורד שלו לא רץ? [{e}])"

        transcript.append({"label": agent["label"], "reply": reply})
        prior_context += f"\n{agent['label']}: {reply}\n"

    return jsonify({"transcript": transcript})


if __name__ == "__main__":
    app.run(port=5099, debug=True)
