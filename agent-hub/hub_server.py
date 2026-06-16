"""Agent Hub — single landing page listing every local agent's status.

Convention: each agent writes its own data/status.json:
    {"name": "...", "status": "running|idle|offline", "last_action": "...", "timestamp": "...", "url": "http://localhost:PORT"}
Hub never talks to an agent directly — it only reads these files, so a dead
or unmodified agent just shows as "no status file yet" instead of crashing the hub.
"""
import json
from pathlib import Path
from flask import Flask, render_template

app = Flask(__name__)

ROOT = Path(__file__).resolve().parent.parent

AGENTS = [
    {"key": "jimmy", "label": "Jimmy (Trading)", "status_file": ROOT / "ninjatrader-mcp" / "data" / "status.json", "url": "http://localhost:5000"},
    {"key": "business-scout", "label": "Business Scout", "status_file": ROOT / "business-scout" / "data" / "status.json", "url": "http://localhost:5001"},
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


if __name__ == "__main__":
    app.run(port=5099, debug=True)
