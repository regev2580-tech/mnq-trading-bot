"""
max_web.py — מקס Web Dashboard + Chat
גישה מ-http://localhost:5001 בכל עת

מבנה זהה ל-ninjatrader-mcp/jimmy_web.py (status + chat + dashboard),
אבל הפרסונה והפעולות מותאמות לחיפוש הזדמנויות עסקיות (scout.py) במקום מסחר.
"""
import json
import os
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta

import anthropic
from flask import Flask, jsonify, request, render_template_string

from scout import run_scout, get_latest_report, get_explored_domains, STATUS_FILE

ISRAEL_TZ = timezone(timedelta(hours=3))
BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.config["JSON_ENSURE_ASCII"] = False

max_state = {
    "status": "online",
    "scanning": False,
    "started_at": datetime.now(ISRAEL_TZ).isoformat(),
}

chat_history: list[dict] = []

MAX_CHAT_SYSTEM = """אתה מקס — סוכן שמחפש הזדמנויות עסקיות דיגיטליות. אתה מדבר ישירות עם היזם שלך בעברית.
אתה יצירתי ופתוח-ראש — לא נצמד לתחום אחד. אתה סורק תחומים מגוונים (בריאות, חינוך, B2B,
תחביבים, שירותים מקומיים, פיננסים ועוד), מזהה כאבים אמיתיים, ומציע מוצר קונקרטי + מודל תמחור
(retainer חודשי או רכישה חד-פעמית).
ענה בצורה ישירה, קצרה, כמו יזם מנוסה — לא כמו בוט.

אם מבקשים ממך לסרוק/לחפש הזדמנויות ("תרוץ סקאן", "סרוק", "תחפש הזדמנות") —
אשר שאתה מתחיל, וה-API יבצע את הסקאן בפועל.
אם מציינים תחום ספציפי ("סקאן בתחום כלבים") — תתמקד בו.
אחרת תבחר תחומים בעצמך, באופן יצירתי, ותעדכן.
"""


def build_chat_context() -> str:
    ctx = [f"⏰ שעה: {datetime.now(ISRAEL_TZ).strftime('%H:%M')} | יום: {datetime.now(ISRAEL_TZ).strftime('%A %Y-%m-%d')}"]
    ctx.append(f"🔍 סורק כרגע: {'כן' if max_state['scanning'] else 'לא'}")

    explored = get_explored_domains()
    if explored:
        ctx.append(f"\n📂 תחומים שנסקרו לאחרונה: {', '.join(explored[-15:])}")

    latest = get_latest_report()
    if latest:
        ctx.append(f"\n📋 הדוח האחרון שלי ({latest.get('date')} {latest.get('time')}):")
        ctx.append(f"תחומים שנסקרו: {', '.join(latest.get('domains_explored', []))}")
        ctx.append(latest.get("report", "")[:1500])

    return "\n".join(ctx)


def _trigger_scan(forced_domain: str | None = None) -> str:
    max_state["scanning"] = True
    try:
        report = run_scout(forced_domain)
    finally:
        max_state["scanning"] = False
    if report.get("error"):
        return f"הסקאן נכשל: {report['error']}"
    return f"סקאן הושלם — תחומים: {', '.join(report.get('domains_explored', []))}\n\n{report.get('report', '')[:1500]}"


def max_chat(user_message: str) -> str:
    lower = user_message.lower()

    scan_triggers = ["תרוץ סקאן", "סרוק", "תחפש הזדמנות", "scan:", "תעשה סקאן"]
    if any(t in lower or t in user_message for t in scan_triggers):
        forced = None
        if ":" in user_message:
            tail = user_message.split(":", 1)[1].strip()
            if tail:
                forced = tail
        chat_history.append({"role": "user", "content": user_message, "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
        result = _trigger_scan(forced)
        chat_history.append({"role": "assistant", "content": result, "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
        return result

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    context = build_chat_context()

    messages = [{"role": m["role"], "content": m["content"]} for m in chat_history[-12:]]
    messages.append({"role": "user", "content": f"[context]\n{context}\n\n[הודעה]\n{user_message}"})

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=800,
        system=MAX_CHAT_SYSTEM,
        messages=messages,
    )
    reply = response.content[0].text.strip()

    chat_history.append({"role": "user", "content": user_message, "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
    chat_history.append({"role": "assistant", "content": reply, "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
    return reply


DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>מקס — Business Scout</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #f6f7fb; color: #1c1f2e; font-family: 'Segoe UI', sans-serif; height: 100vh; display: flex; flex-direction: column; }
.header { background: #ffffff; border-bottom: 1px solid #e7e9f0; padding: 12px 20px; display: flex; align-items: center; justify-content: space-between; }
.header h1 { font-size: 18px; } .header h1 span { color: #c98a17; }
.status-badge { padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: #fbf1de; color: #c98a17; }
.main { display: flex; flex: 1; overflow: hidden; }
.left { width: 360px; flex-shrink: 0; border-left: 1px solid #e7e9f0; padding: 14px; overflow-y: auto; background: #ffffff; }
.left h3 { font-size: 12px; color: #8a8fa3; text-transform: uppercase; margin: 14px 0 6px; }
.left .domains { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { background: #f1f2f8; border: 1px solid #e7e9f0; border-radius: 12px; padding: 3px 9px; font-size: 11px; color: #5b5f73; }
.report-box { background: #fafbfd; border: 1px solid #e7e9f0; border-radius: 8px; padding: 10px; font-size: 12px; white-space: pre-wrap; line-height: 1.6; max-height: 50vh; overflow-y: auto; color: #1c1f2e; }
.chat-panel { flex: 1; display: flex; flex-direction: column; }
.chat-messages { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.msg { max-width: 78%; padding: 10px 13px; border-radius: 14px; font-size: 13px; line-height: 1.6; white-space: pre-wrap; }
.msg.user { background: #4f6df5; color: white; align-self: flex-end; border-radius: 14px 14px 4px 14px; }
.msg.max { background: #f1f2f8; border: 1px solid #e7e9f0; align-self: flex-start; border-radius: 14px 14px 14px 4px; color: #1c1f2e; }
.msg.max .who { font-size: 11px; color: #c98a17; font-weight: 700; margin-bottom: 4px; }
.chat-input-row { padding: 10px; border-top: 1px solid #e7e9f0; display: flex; gap: 8px; background: #ffffff; }
.chat-input { flex: 1; background: #fafbfd; border: 1px solid #e7e9f0; border-radius: 8px; color: #1c1f2e; padding: 9px 12px; font-size: 13px; outline: none; resize: none; font-family: inherit; }
.send-btn { background: #4f6df5; border: none; color: white; border-radius: 8px; padding: 9px 16px; cursor: pointer; font-weight: 600; }
.quick-btns { padding: 6px 10px; border-top: 1px solid #f1f2f8; display: flex; flex-wrap: wrap; gap: 5px; }
.qbtn { background: #f1f2f8; border: 1px solid #e7e9f0; color: #5b5f73; border-radius: 14px; padding: 4px 10px; font-size: 11px; cursor: pointer; }
</style>
</head>
<body>
<div class="header">
  <h1>🧭 <span>מקס</span> — Business Scout</h1>
  <span class="status-badge" id="status-badge">טוען...</span>
</div>
<div class="main">
  <div class="left">
    <h3>תחומים שנסקרו לאחרונה</h3>
    <div class="domains" id="domains-box">—</div>
    <h3>הדוח האחרון</h3>
    <div class="report-box" id="report-box">אין עדיין דוח. בקש ממקס לסרוק.</div>
  </div>
  <div class="chat-panel">
    <div class="chat-messages" id="chat-messages">
      <div class="msg max"><div class="who">מקס</div>שלום! אני מקס 🧭<br>אני מחפש הזדמנויות עסקיות בתחומים מגוונים.<br><br>בקש ממני: "תרוץ סקאן" (אני בוחר תחומים) או "סקאן: שם תחום" (תחום ספציפי).</div>
    </div>
    <div class="quick-btns">
      <button class="qbtn" onclick="sendQuick('תרוץ סקאן')">🔍 תרוץ סקאן</button>
      <button class="qbtn" onclick="sendQuick('מה הדוח האחרון?')">דוח אחרון</button>
      <button class="qbtn" onclick="sendQuick('אילו תחומים סרקת?')">תחומים שנסקרו</button>
    </div>
    <div class="chat-input-row">
      <textarea class="chat-input" id="chat-input" rows="2" placeholder="דבר עם מקס..."
        onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChat();}"></textarea>
      <button class="send-btn" onclick="sendChat()">שלח</button>
    </div>
  </div>
</div>
<script>
async function fetchStatus() {
  try {
    const d = await (await fetch('/api/status')).json();
    document.getElementById('status-badge').textContent = d.scanning ? 'סורק...' : 'online';
    if (d.domains_explored) {
      document.getElementById('domains-box').innerHTML = d.domains_explored.map(x=>`<span class="tag">${x}</span>`).join('') || '—';
    }
    if (d.latest_report) {
      document.getElementById('report-box').textContent = d.latest_report;
    }
  } catch(e){}
}
async function sendChat() {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if(!msg) return;
  input.value='';
  addMsg('user', msg);
  const typingId = 'typing-'+Date.now();
  addMsg('max', '...', typingId);
  try {
    const r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message: msg})});
    const d = await r.json();
    document.getElementById(typingId)?.remove();
    addMsg('max', d.reply||'שגיאה');
    fetchStatus();
  } catch(e) {
    document.getElementById(typingId)?.remove();
    addMsg('max', '❌ שגיאת חיבור');
  }
}
function sendQuick(msg){ document.getElementById('chat-input').value = msg; sendChat(); }
function addMsg(role, text, id) {
  const box = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'msg '+role;
  if(id) div.id = id;
  if(role==='max') div.innerHTML = `<div class="who">מקס</div>${text.replace(/\n/g,'<br>')}`;
  else div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}
fetchStatus();
setInterval(fetchStatus, 8000);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/status")
def api_status():
    latest = get_latest_report()
    return jsonify({
        **max_state,
        "domains_explored": get_explored_domains()[-15:],
        "latest_report": latest.get("report", ""),
    })


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"reply": "?"}), 400
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return jsonify({"reply": "❌ ANTHROPIC_API_KEY לא מוגדר"}), 500
    try:
        reply = max_chat(message)
        return jsonify({"reply": reply, "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
    except Exception as e:
        return jsonify({"reply": f"❌ שגיאה: {e}"}), 500


@app.route("/api/scan", methods=["POST"])
def api_scan():
    data = request.get_json(silent=True) or {}
    forced = data.get("domain")
    result = _trigger_scan(forced)
    return jsonify({"ok": True, "result": result})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)
