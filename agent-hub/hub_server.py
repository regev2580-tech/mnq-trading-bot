"""Agent Hub — single landing page listing every local agent's status.

Convention: each agent writes its own data/status.json:
    {"name": "...", "status": "running|idle|offline", "last_action": "...", "timestamp": "...", "url": "http://127.0.0.1:PORT"}
Hub never talks to an agent directly — it only reads these files, so a dead
or unmodified agent just shows as "no status file yet" instead of crashing the hub.
"""
import json
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

ROOT = Path(__file__).resolve().parent.parent

AGENTS = [
    {
        "key": "jimmy",
        "label": "ג'ימי (מסחר)",
        "status_file": ROOT / "ninjatrader-mcp" / "data" / "status.json",
        "url": "http://127.0.0.1:5000",
        "chat_url": "http://127.0.0.1:5000/api/chat",
    },
    {
        "key": "max",
        "label": "מקס (הזדמנויות עסקיות)",
        "status_file": ROOT / "business-scout" / "data" / "status.json",
        "url": "http://127.0.0.1:5001",
        "chat_url": "http://127.0.0.1:5001/api/chat",
    },
    {
        "key": "sean",
        "label": "שון (מפקח BeautyAI)",
        "status_file": ROOT / "sean" / "data" / "status.json",
        "url": "http://127.0.0.1:5002",
        "chat_url": "http://127.0.0.1:5002/api/chat",
    },
]


def check_agent_online(agent: dict) -> bool:
    """TCP socket check — מהיר יותר מ-HTTP ולא מצריך את הסוכן לענות על /api/status."""
    try:
        parsed = urlparse(agent["url"])
        port = parsed.port or 80
        s = socket.create_connection((parsed.hostname, port), timeout=1)
        s.close()
        return True
    except Exception:
        return False


def load_status(agent):
    online = check_agent_online(agent)
    f = agent["status_file"]
    if not f.exists():
        return {"status": "online" if online else "offline",
                "last_action": "רץ (אין status.json)" if online else "לא הופעל עדיין",
                "timestamp": "-", "online": online}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        data["online"] = online
        if not online:
            data["status"] = "offline"
        return data
    except (json.JSONDecodeError, OSError):
        return {"status": "online" if online else "offline",
                "last_action": "-", "timestamp": "-", "online": online}


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


@app.route("/api/agents-status")
def api_agents_status():
    """מחזיר מצב online/offline — כל הפינגים במקביל."""
    def _check(agent):
        info = load_status(agent)
        return {
            "key": agent["key"],
            "label": agent["label"],
            "url": agent["url"],
            "online": info.get("online", False),
            "last_action": info.get("last_action", "-"),
            "timestamp": info.get("timestamp", "-"),
        }

    with ThreadPoolExecutor(max_workers=len(AGENTS)) as ex:
        results = list(ex.map(_check, AGENTS))
    return jsonify(results)


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
    app.run(host="0.0.0.0", port=5100, debug=False, use_reloader=False)
