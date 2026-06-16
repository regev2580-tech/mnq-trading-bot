"""
jimmy_web.py — ג'ימי Web Dashboard + Chat
גישה מ-http://localhost:5000 בכל עת
"""

import json
import threading
import anthropic
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request, send_file, render_template_string

ISRAEL_TZ  = timezone(timedelta(hours=3))
BASE_DIR   = Path(r"C:\Users\DELL\New folder\ninjatrader-mcp")
DATA_DIR   = BASE_DIR / "data"
LOG_FILE   = DATA_DIR / "jimmy_log.txt"
BRAIN_FILE = DATA_DIR / "jimmy_brain.json"

app = Flask(__name__)
app.config["JSON_ENSURE_ASCII"] = False

# State משותף עם jimmy.py
jimmy_state = {
    "status":           "starting",
    "current_price":    None,
    "last_analysis":    None,
    "last_decision":    None,
    "screenshot_b64":   None,
    "trades_today":     0,
    "signals":          [],
    "score":            0,
    "cvd":              0,
    "orderflow":        None,
    "tv_context":       None,
    "htf_bias":         "UNKNOWN",
    "tv_connected":     False,
    "started_at":       datetime.now(ISRAEL_TZ).isoformat(),
    "stop_requested":   False,
    "force_analysis":   False,
    "shutdown_requested": False,
    "next_kz":          "",
    "today_events":     {},        # לוח כלכלי
    "daily_plan":       "",        # תכנית סשן
    "session_review":   "",        # סיכום סשן
}

# היסטוריית צ'אט — נשמרת בין sessions
chat_history: list[dict] = []


# ──────────────────────────────────────────────
# Brain — זיכרון קבוע של ג'ימי
# ──────────────────────────────────────────────

def load_brain() -> dict:
    try:
        return json.loads(BRAIN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"lessons": [], "rules_override": [], "trade_notes": []}


def save_brain(brain: dict):
    brain["updated_at"] = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d %H:%M")
    BRAIN_FILE.write_bytes(json.dumps(brain, ensure_ascii=False, indent=2).encode("utf-8"))


def add_lesson(text: str, category: str = "general") -> str:
    brain = load_brain()
    lesson = {
        "id":       len(brain["lessons"]) + 1,
        "text":     text,
        "category": category,
        "date":     datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d %H:%M"),
    }
    brain["lessons"].append(lesson)
    save_brain(brain)
    return f"✅ נשמר (#{lesson['id']}): {text}"


def forget_lesson(lesson_id: int) -> str:
    brain = load_brain()
    before = len(brain["lessons"])
    brain["lessons"] = [l for l in brain["lessons"] if l.get("id") != lesson_id]
    if len(brain["lessons"]) < before:
        save_brain(brain)
        return f"✅ שכחתי lesson #{lesson_id}"
    return f"לא מצאתי lesson #{lesson_id}"


def format_brain_for_context(brain: dict) -> str:
    if not brain["lessons"] and not brain["rules_override"]:
        return ""
    lines = ["\n📚 מה שלמדתי (הזיכרון שלי):"]
    for l in brain["lessons"][-20:]:   # 20 לקחים אחרונים
        lines.append(f"  [{l['date']}] {l['text']}")
    if brain.get("rules_override"):
        lines.append("\n⚡ כללים מיוחדים:")
        for r in brain["rules_override"]:
            lines.append(f"  • {r}")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Chat Engine
# ──────────────────────────────────────────────

JIMMY_CHAT_SYSTEM = """אתה ג'ימי — סוכן מסחר אוטונומי על MNQ. אתה מדבר ישירות עם הסוחר שלך בעברית.
אתה זמין 24/7 — גם כשאין מסחר, אתה כאן לדון, לנתח, וללמוד.
אתה מכיר ICT 2022 + Valtos Order Flow + את כל הלקחים שלמדת מהעסקאות.
ענה בצורה ישירה, קצרה, כמו סוחר מקצועי — לא כמו בוט.

כשמלמדים אותך משהו חדש ("זכור", "למד", "שמור"):
→ אשר שתשמור, ובאותו רגע ה-API שומר לצמיתות.

כשמבקשים ניתוח שוק — נתח לפי הנתונים שקיבלת.
כשנותנים פקודה (עצור / שנה bias / נתח) — תאשר ובצע.
כשממליץ על עסקה — תמיד כלול entry, SL, TP, R/R.
כשאין נתוני שוק (שוק סגור) — דון, נתח היסטוריה, תכנן.
"""

def build_chat_context() -> str:
    """בנה context מלא לצ'אט — כל מה שג'ימי יודע עכשיו"""
    now = datetime.now(ISRAEL_TZ).strftime("%H:%M")
    ctx = [f"⏰ שעה: {now} ישראל | יום: {datetime.now(ISRAEL_TZ).strftime('%A %Y-%m-%d')}"]

    # מצב ג'ימי
    status_map = {
        "waiting": "ממתין ל-Kill Zone",
        "analyzing": "מנתח שוק",
        "signal_sent": "signal נשלח",
        "stopped": "עצר",
    }
    ctx.append(f"🤖 מצב ג'ימי: {status_map.get(jimmy_state['status'], jimmy_state['status'])}")
    ctx.append(f"📊 עסקאות היום: {jimmy_state['trades_today']} / 2")
    ctx.append(f"🎯 HTF Bias: {jimmy_state['htf_bias']}")

    # OrderFlow
    of = jimmy_state.get("orderflow")
    if of:
        ctx.append(f"\n📈 OrderFlow:")
        ctx.append(f"  מחיר: {of.get('price')}")
        ctx.append(f"  Valtos Score: {jimmy_state.get('score', 0):+d}")
        ctx.append(f"  CVD (10 bars): {round(jimmy_state.get('cvd', 0))}")
        ctx.append(f"  Delta נוכחי: {of.get('current_delta', 0):+d}")
        ctx.append(f"  CDH: {of.get('cdh')} | CDL: {of.get('cdl')}")
        ctx.append(f"  PDH: {of.get('pdh')} | PDL: {of.get('pdl')}")

        bars = of.get("bars", [])
        if bars:
            ctx.append(f"\n  3 בארים אחרונים:")
            for b in bars[:3]:
                ctx.append(f"    {b['time']}: close={b['c']} delta={b['delta']:+d} vol={b['total_vol']:,}")

    # החלטה אחרונה
    if jimmy_state.get("last_decision"):
        ctx.append(f"\n🤖 החלטה אחרונה: {jimmy_state['last_decision']}")

    # Signals היום
    signals = jimmy_state.get("signals", [])
    if signals:
        ctx.append(f"\n✅ Signals היום:")
        for s in signals:
            ctx.append(f"  {s['time']}: {s['action']} @ {s['entry']} | SL={s['sl']} | TP={s['tp']} | R/R={s['rr']}")

    # פוזיציה פתוחה
    pos_file = DATA_DIR / "position.json"
    try:
        pos = json.loads(pos_file.read_text(encoding="utf-8"))
        if pos.get("status") == "open":
            ctx.append(f"\n📊 פוזיציה פתוחה: {pos.get('direction')} @ {pos.get('entry')}")
    except Exception:
        pass

    # לוח כלכלי
    events = jimmy_state.get("today_events", {})
    if events:
        ctx.append(f"\n📅 לוח כלכלי היום:")
        ctx.append(f"  {events.get('summary','לא נבדק')}")
        if events.get("has_high_impact"):
            ctx.append(f"  ⚠️ HIGH IMPACT! Decision: {events.get('trading_decision','')}")
        for ev in events.get("events", [])[:3]:
            ctx.append(f"  {ev}")

    # תכנית סשן
    plan = jimmy_state.get("daily_plan", "")
    if plan:
        ctx.append(f"\n📋 תכנית הסשן שלי:")
        ctx.append(plan[:400])

    # סיכום סשן
    review = jimmy_state.get("session_review", "")
    if review:
        ctx.append(f"\n🏁 סיכום סשן:")
        ctx.append(review[:300])

    # 10 שורות לוג אחרונות
    try:
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        if lines:
            ctx.append(f"\n📋 לוג אחרון:")
            for line in lines[-10:]:
                ctx.append(f"  {line}")
    except Exception:
        pass

    return "\n".join(ctx)


def jimmy_chat(user_message: str) -> str:
    """שלח הודעה לג'ימי וקבל תשובה"""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    # טפל בפקודות זיכרון לפני שליחה לקלוד
    lower = user_message.lower()
    if any(w in lower for w in ["זכור:", "למד:", "שמור:", "remember:"]):
        # חלץ את הטקסט אחרי ":"
        for prefix in ["זכור:", "למד:", "שמור:", "remember:"]:
            if prefix in lower:
                idx   = user_message.lower().index(prefix) + len(prefix)
                lesson = user_message[idx:].strip()
                if lesson:
                    result = add_lesson(lesson)
                    chat_history.append({"role": "user",      "content": user_message, "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
                    chat_history.append({"role": "assistant", "content": result,        "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
                    return result

    # בקשות מחקר מהרשת
    # סטטיסטיקות למידה
    if any(w in lower for w in ["כמה למדת", "סטטיסטיקות למידה", "כמה נושאים", "learning stats"]):
        try:
            from jimmy_research import get_learning_stats
            stats = get_learning_stats()
            reply = (f"📚 למדתי עד כה: {stats['learned_count']}/{stats['total_available']} נושאים "
                     f"({stats['percentage']}%)\n"
                     f"למידה אחרונה: {stats['last_learned']}\n\n"
                     f"לומד 5 נושאים חדשים כל יום — ב-10:00, 12:00, 14:00, 19:30, 21:00")
            chat_history.append({"role": "user",      "content": user_message, "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
            chat_history.append({"role": "assistant", "content": reply,        "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
            return reply
        except Exception as e:
            pass

    if any(w in lower for w in ["חקור:", "research:", "חפש ברשת:", "למד על:"]):
        for prefix in ["חקור:", "research:", "חפש ברשת:", "למד על:"]:
            if prefix in lower:
                idx   = user_message.lower().index(prefix) + len(prefix)
                topic = user_message[idx:].strip()
                if topic:
                    try:
                        from jimmy_research import research_concept
                        result = research_concept(topic)
                        chat_history.append({"role": "user",      "content": user_message, "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
                        chat_history.append({"role": "assistant", "content": result,        "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
                        return result
                    except Exception as e:
                        return f"שגיאת מחקר: {e}"

    if "מה אתה זוכר" in user_message or "הראה זיכרון" in user_message:
        brain = load_brain()
        if not brain["lessons"]:
            return "אין לי עדיין לקחים שמורים. למד אותי: 'זכור: ...'"
        lines = ["📚 הלקחים שלי:"]
        for l in brain["lessons"]:
            lines.append(f"  #{l['id']} [{l['date']}] {l['text']}")
        return "\n".join(lines)

    if "שכח" in user_message and "#" in user_message:
        try:
            num = int(user_message.split("#")[1].split()[0])
            result = forget_lesson(num)
            chat_history.append({"role": "user", "content": user_message, "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
            chat_history.append({"role": "assistant", "content": result, "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
            return result
        except Exception:
            pass

    # טען brain + context
    brain   = load_brain()
    context = build_chat_context()
    brain_ctx = format_brain_for_context(brain)

    full_context = context + brain_ctx

    # בנה messages — היסטוריה + הודעה נוכחית
    messages = []
    for msg in chat_history[-12:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({
        "role": "user",
        "content": f"[context]\n{full_context}\n\n[הודעה]\n{user_message}"
    })

    response = client.messages.create(
        model      = "claude-haiku-4-5",   # זול x20 לצ'אט רגיל
        max_tokens = 800,
        system     = JIMMY_CHAT_SYSTEM,
        messages   = messages,
    )

    reply = response.content[0].text.strip()

    # שמור בהיסטוריה
    chat_history.append({"role": "user",      "content": user_message, "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
    chat_history.append({"role": "assistant", "content": reply,        "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})

    # בצע פקודות אוטומטיות
    _handle_chat_command(reply, user_message)

    return reply


def _handle_chat_command(reply: str, user_msg: str):
    """בדוק אם ההודעה כוללת פקודה לביצוע"""
    u = user_msg.lower()
    if any(w in u for w in ["עצור", "stop", "תעצור"]):
        jimmy_state["stop_requested"] = True
    if any(w in u for w in ["נתח", "force", "ניתוח עכשיו"]):
        jimmy_state["force_analysis"] = True
    if "bullish" in u.lower():
        _update_bias("BULLISH")
    elif "bearish" in u.lower():
        _update_bias("BEARISH")


def _update_bias(new_bias: str):
    bias_file = DATA_DIR / "session_bias.json"
    try:
        data = json.loads(bias_file.read_text(encoding="utf-8"))
        data["htf_bias"] = new_bias
        data["set_at"]   = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d %H:%M")
        bias_file.write_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        jimmy_state["htf_bias"] = new_bias
    except Exception:
        pass


# ──────────────────────────────────────────────
# HTML Dashboard
# ──────────────────────────────────────────────

DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ג'ימי — Trading Agent</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #f6f7fb; color: #1c1f2e; font-family: 'Segoe UI', sans-serif; height: 100vh; display: flex; flex-direction: column; }

.header { background: #ffffff; border-bottom: 1px solid #e7e9f0; padding: 12px 20px;
  display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
.header h1 { font-size: 18px; font-weight: 700; }
.header h1 span { color: #4f6df5; }

.status-badge { padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.status-waiting   { background: #eef1ff; color: #4f6df5; }
.status-analyzing { background: #e6f7ef; color: #1aa96e; animation: pulse 1.5s infinite; }
.status-signal    { background: #fdecee; color: #e24c5c; }
.status-stopped   { background: #f1f2f8; color: #8a8fa3; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.6} }

.main { display: flex; flex: 1; overflow: hidden; }

/* ── LEFT PANEL ── */
.left { width: 340px; flex-shrink: 0; border-left: 1px solid #e7e9f0;
  display: flex; flex-direction: column; overflow: hidden; background: #ffffff; }

.metrics { padding: 12px; border-bottom: 1px solid #e7e9f0; }
.metric { display: flex; justify-content: space-between; padding: 5px 0;
  border-bottom: 1px solid #f1f2f8; font-size: 13px; }
.metric:last-child { border: none; }
.lbl { color: #8a8fa3; }
.val { font-weight: 600; color: #1c1f2e; }
.bull { color: #1aa96e; } .bear { color: #e24c5c; } .neutral { color: #1c1f2e; }

.section-title { padding: 8px 12px; font-size: 11px; color: #8a8fa3;
  text-transform: uppercase; letter-spacing: 1px; background: #fafbfd;
  border-bottom: 1px solid #e7e9f0; }

.log-box { flex: 1; overflow-y: auto; padding: 8px 12px; background: #fafbfd;
  font-family: Consolas, monospace; font-size: 11px; line-height: 1.7; }
.log-l { color: #8a8fa3; }
.log-l.s { color: #1aa96e; font-weight: 600; }
.log-l.e { color: #e24c5c; }
.log-l.a { color: #4f6df5; }

/* ── CENTER PANEL ── */
.center { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.tv-panel { flex: 1; overflow: hidden; position: relative; background: #eef0f6; }
.tv-panel img { width: 100%; height: 100%; object-fit: contain; }
.tv-placeholder { display: flex; align-items: center; justify-content: center;
  height: 100%; color: #8a8fa3; font-size: 14px; }

.signals-bar { padding: 10px 14px; border-top: 1px solid #e7e9f0;
  background: #ffffff; min-height: 50px; }
.sig-item { display: inline-block; background: #fafbfd; border: 1px solid #e7e9f0;
  border-radius: 6px; padding: 4px 10px; margin: 3px; font-size: 12px; }
.sig-buy { border-color: #1aa96e; color: #1aa96e; }
.sig-short { border-color: #e24c5c; color: #e24c5c; }

/* ── CHAT PANEL ── */
.chat-panel { width: 360px; flex-shrink: 0; border-right: 1px solid #e7e9f0;
  display: flex; flex-direction: column; background: #ffffff; }

.chat-messages { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 10px; }

.msg { max-width: 88%; padding: 10px 13px; border-radius: 14px; font-size: 13px; line-height: 1.6; }
.msg.user { background: #4f6df5; color: white; align-self: flex-end; border-radius: 14px 14px 4px 14px; }
.msg.jimmy { background: #f1f2f8; border: 1px solid #e7e9f0; align-self: flex-start; color: #1c1f2e;
  border-radius: 14px 14px 14px 4px; white-space: pre-wrap; }
.msg.jimmy .who { font-size: 11px; color: #4f6df5; font-weight: 700; margin-bottom: 4px; }
.msg.time { font-size: 10px; color: #8a8fa3; align-self: center; }

.chat-input-row { padding: 10px; border-top: 1px solid #e7e9f0; display: flex; gap: 8px; background: #ffffff; }
.chat-input { flex: 1; background: #fafbfd; border: 1px solid #e7e9f0; border-radius: 8px;
  color: #1c1f2e; padding: 9px 12px; font-size: 13px; outline: none; font-family: inherit; resize: none; }
.chat-input:focus { border-color: #4f6df5; }
.send-btn { background: #4f6df5; border: none; color: white; border-radius: 8px;
  padding: 9px 16px; cursor: pointer; font-size: 13px; font-weight: 600; }
.send-btn:hover { background: #3d57d6; }
.send-btn:disabled { background: #e7e9f0; color: #8a8fa3; cursor: default; }

.quick-btns { padding: 6px 10px; border-top: 1px solid #f1f2f8; display: flex; flex-wrap: wrap; gap: 5px; }
.qbtn { background: #f1f2f8; border: 1px solid #e7e9f0; color: #5b5f73; border-radius: 14px;
  padding: 4px 10px; font-size: 11px; cursor: pointer; }
.qbtn:hover { background: #e7e9f0; color: #1c1f2e; }

.ctrl-btns { display: flex; gap: 6px; }
.btn { padding: 6px 14px; border: none; border-radius: 6px; cursor: pointer;
  font-size: 12px; font-weight: 600; }
.btn-red   { background: #e24c5c; color: white; }
.btn-blue  { background: #4f6df5; color: white; }
.btn:hover { opacity: 0.85; }
</style>
</head>
<body>

<div class="header">
  <h1>🤖 <span>ג'ימי</span> — Trading Agent</h1>
  <div style="display:flex;align-items:center;gap:10px">
    <span id="status-badge" class="status-badge status-waiting">טוען...</span>
    <div class="ctrl-btns">
      <button class="btn btn-blue" onclick="sendQuick('נתח את השוק עכשיו')">ניתוח</button>
      <button class="btn" style="background:#238636;color:white" onclick="refreshTV()" id="tv-btn">📸 TV</button>
      <button class="btn btn-red"  onclick="sendQuick('עצור')">עצור</button>
    </div>
  </div>
</div>

<div class="main">

  <!-- LEFT: מדדים + לוג -->
  <div class="left">
    <div class="metrics">
      <div class="metric"><span class="lbl">מחיר</span>      <span class="val neutral" id="m-price">—</span></div>
      <div class="metric"><span class="lbl">Score</span>     <span class="val" id="m-score">—</span></div>
      <div class="metric"><span class="lbl">CVD</span>       <span class="val" id="m-cvd">—</span></div>
      <div class="metric"><span class="lbl">Delta</span>     <span class="val" id="m-delta">—</span></div>
      <div class="metric"><span class="lbl">CDH</span>       <span class="val neutral" id="m-cdh">—</span></div>
      <div class="metric"><span class="lbl">CDL</span>       <span class="val neutral" id="m-cdl">—</span></div>
      <div class="metric"><span class="lbl">Bias</span>      <span class="val" id="m-bias">—</span></div>
      <div class="metric"><span class="lbl">TV</span>        <span class="val" id="m-tv">—</span></div>
      <div class="metric"><span class="lbl">עסקאות</span>   <span class="val neutral" id="m-trades">0/2</span></div>
    </div>
    <div class="section-title">לוג</div>
    <div class="log-box" id="log-box"></div>
  </div>

  <!-- CENTER: TV Chart + Signals -->
  <div class="center">
    <div class="tv-panel">
      <img id="tv-img" src="" style="display:none" alt="TV">
      <div class="tv-placeholder" id="tv-placeholder">📊 ממתין לצילום מסך מ-TradingView...</div>
    </div>
    <div class="signals-bar">
      <span style="color:#8b949e;font-size:11px;margin-left:8px">Signals:</span>
      <span id="signals-inline"><span style="color:#6e7681;font-size:12px">אין signals היום</span></span>
    </div>
  </div>

  <!-- RIGHT: Chat עם ג'ימי -->
  <div class="chat-panel">
    <div class="section-title">💬 דבר עם ג'ימי</div>
    <div class="chat-messages" id="chat-messages">
      <div class="msg jimmy">
        <div class="who">ג'ימי</div>
        שלום! אני ג'ימי 🤖<br>
        שאל אותי כל שאלה על השוק, ותן לי הוראות.<br><br>
        לדוגמה:<br>
        • "מה המצב בשוק?"<br>
        • "למה לא נכנסת?"<br>
        • "שנה bias ל-BULLISH"<br>
        • "תסגור פוזיציה"
      </div>
    </div>
    <div class="quick-btns">
      <button class="qbtn" onclick="sendQuick('מה המצב בשוק?')">מה המצב?</button>
      <button class="qbtn" onclick="sendQuick('למה לא נכנסת עדיין?')">למה לא נכנסת?</button>
      <button class="qbtn" onclick="sendQuick('מה ה-score עכשיו?')">Score</button>
      <button class="qbtn" onclick="sendQuick('מה הלוח הכלכלי היום?')">לוח כלכלי</button>
      <button class="qbtn" onclick="sendQuick('מה התכנית שלך לסשן היום?')">תכנית סשן</button>
      <button class="qbtn" onclick="sendQuick('כמה למדת עד עכשיו?')">כמה למדת?</button>
      <button class="qbtn" onclick="sendQuick('מה אתה זוכר?')">מה זוכר?</button>
      <button class="qbtn" onclick="sendQuick('שנה bias ל-BULLISH')">→ BULLISH</button>
      <button class="qbtn" onclick="sendQuick('שנה bias ל-BEARISH')">→ BEARISH</button>
      <button class="qbtn" onclick="sendQuick('נתח את השוק עכשיו')">נתח עכשיו</button>
      <button class="qbtn" onclick="sendQuick('מה היה בסשן היום?')">סיכום</button>
    </div>
    <div class="chat-input-row">
      <textarea class="chat-input" id="chat-input" rows="2"
        placeholder="שאל את ג'ימי..."
        onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChat();}"></textarea>
      <button class="send-btn" id="send-btn" onclick="sendChat()">שלח</button>
    </div>
  </div>

</div>

<script>
let lastLog = 0;

// ── Status polling ──
async function fetchStatus() {
  try {
    const d = await (await fetch('/api/status')).json();
    updateMetrics(d);
  } catch(e){}
}

function updateMetrics(d) {
  const badge = document.getElementById('status-badge');
  const sm = {waiting:'ממתין',analyzing:'מנתח...',signal_sent:'Signal!',stopped:'עצר',starting:'מתחיל'};
  const sc = {waiting:'status-waiting',analyzing:'status-analyzing',signal_sent:'status-signal',stopped:'status-stopped',starting:'status-waiting'};
  badge.textContent = sm[d.status]||d.status;
  badge.className   = 'status-badge '+(sc[d.status]||'status-waiting');

  const of = d.orderflow||{};
  set('m-price', of.price ? of.price.toLocaleString() : '—', 'neutral');

  const sc2 = d.score||0;
  set('m-score', (sc2>0?'+':'')+sc2, sc2>=3?'bull':sc2<=-3?'bear':'neutral');

  const cvd = d.cvd||0;
  set('m-cvd', (cvd>0?'+':'')+Math.round(cvd).toLocaleString(), cvd>500?'bull':cvd<-500?'bear':'neutral');

  const dl = of.current_delta||0;
  set('m-delta', (dl>0?'+':'')+dl.toLocaleString(), dl>0?'bull':dl<0?'bear':'neutral');

  document.getElementById('m-cdh').textContent = of.cdh||'—';
  document.getElementById('m-cdl').textContent = of.cdl||'—';

  const bias = d.htf_bias||'UNKNOWN';
  set('m-bias', bias, bias==='BULLISH'?'bull':bias==='BEARISH'?'bear':'neutral');
  set('m-tv', d.tv_connected?'✅ מחובר':'❌ לא מחובר', d.tv_connected?'bull':'bear');
  document.getElementById('m-trades').textContent = (d.trades_today||0)+' / 2';

  // Screenshot
  if (d.screenshot_b64) {
    document.getElementById('tv-img').src = 'data:image/png;base64,'+d.screenshot_b64;
    document.getElementById('tv-img').style.display='block';
    document.getElementById('tv-placeholder').style.display='none';
  }

  // Signals
  const sigs = d.signals||[];
  document.getElementById('signals-inline').innerHTML = sigs.length
    ? sigs.map(s=>`<span class="sig-item ${s.action==='BUY'?'sig-buy':'sig-short'}">${s.action==='BUY'?'▲':'▼'} ${s.time} @ ${s.entry}</span>`).join('')
    : '<span style="color:#6e7681;font-size:12px">אין signals היום</span>';
}

function set(id, val, cls='neutral') {
  const el = document.getElementById(id);
  if(el){ el.textContent=val; el.className='val '+cls; }
}

// ── Log polling ──
async function fetchLog() {
  try {
    const d = await (await fetch('/api/log')).json();
    const lines = d.lines||[];
    if(lines.length===lastLog) return;
    lastLog=lines.length;
    const box=document.getElementById('log-box');
    box.innerHTML=lines.map(l=>{
      let c='log-l';
      if(l.includes('✅')||l.includes('Signal')) c+=' s';
      if(l.includes('❌')||l.includes('שגיאה')) c+=' e';
      if(l.includes('🤖')||l.includes('מנתח'))  c+=' a';
      return `<div class="${c}">${l}</div>`;
    }).join('');
    box.scrollTop=box.scrollHeight;
  } catch(e){}
}

// ── Chat ──
async function sendChat() {
  const input = document.getElementById('chat-input');
  const msg   = input.value.trim();
  if(!msg) return;

  input.value='';
  addMsg('user', msg);

  const btn = document.getElementById('send-btn');
  btn.disabled=true; btn.textContent='...';

  // typing indicator
  const typingId = 'typing-'+Date.now();
  addMsg('jimmy', '...', typingId);

  try {
    const r = await fetch('/api/chat', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message: msg})
    });
    const d = await r.json();
    document.getElementById(typingId)?.remove();
    addMsg('jimmy', d.reply||'שגיאה');
  } catch(e) {
    document.getElementById(typingId)?.remove();
    addMsg('jimmy', '❌ שגיאת חיבור');
  }

  btn.disabled=false; btn.textContent='שלח';
}

function sendQuick(msg) {
  document.getElementById('chat-input').value = msg;
  sendChat();
}

function addMsg(role, text, id) {
  const box  = document.getElementById('chat-messages');
  const now  = new Date().toLocaleTimeString('he-IL',{hour:'2-digit',minute:'2-digit'});
  const div  = document.createElement('div');
  div.className = 'msg '+role;
  if(id) div.id=id;
  if(role==='jimmy') div.innerHTML=`<div class="who">ג'ימי ${now}</div>${text.replace(/\n/g,'<br>')}`;
  else div.textContent = text;
  box.appendChild(div);
  box.scrollTop=box.scrollHeight;
}

// ── TV Refresh ──
async function refreshTV() {
  const btn = document.getElementById('tv-btn');
  btn.textContent = '...';
  try {
    const r = await fetch('/api/tv/refresh');
    const d = await r.json();
    if(d.ok) { btn.textContent = '✅ TV'; setTimeout(()=>btn.textContent='📸 TV',2000); fetchStatus(); }
    else { btn.textContent = '❌ TV'; setTimeout(()=>btn.textContent='📸 TV',3000); }
  } catch(e) { btn.textContent = '❌ TV'; setTimeout(()=>btn.textContent='📸 TV',3000); }
}

// Start
fetchStatus(); fetchLog();
setInterval(fetchStatus, 5000);
setInterval(fetchLog, 6000);
</script>
</body>
</html>
"""


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/status")
def api_status():
    return jsonify(jimmy_state)


@app.route("/api/log")
def api_log():
    try:
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        return jsonify({"lines": lines[-60:], "total": len(lines)})
    except Exception:
        return jsonify({"lines": [], "total": 0})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """צ'אט ישיר עם ג'ימי"""
    data    = request.get_json() or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"reply": "?"}), 400

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return jsonify({"reply": "❌ ANTHROPIC_API_KEY לא מוגדר"}), 500

    try:
        reply = jimmy_chat(message)
        return jsonify({"reply": reply, "time": datetime.now(ISRAEL_TZ).strftime("%H:%M")})
    except Exception as e:
        return jsonify({"reply": f"❌ שגיאה: {str(e)}"}), 500


@app.route("/api/screenshot")
def api_screenshot():
    screenshots = sorted(
        (BASE_DIR / "data" / "screenshots").glob("*.png"),
        key=lambda p: p.stat().st_mtime, reverse=True
    )
    if screenshots:
        return send_file(str(screenshots[0]), mimetype="image/png")
    return "אין screenshot", 404


@app.route("/api/tv/refresh")
def api_tv_refresh():
    """צלם TV עכשיו ועדכן dashboard"""
    try:
        from jimmy_tv import take_screenshot, health_check
        if not health_check():
            jimmy_state["tv_connected"] = False
            return jsonify({"ok": False, "error": "TradingView לא זמין"})
        b64, path = take_screenshot("full")
        jimmy_state["screenshot_b64"] = b64
        jimmy_state["tv_connected"]   = True
        return jsonify({"ok": True, "path": path})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/memory", methods=["GET"])
def api_memory():
    """קבל את כל הזיכרון של ג'ימי"""
    return jsonify(load_brain())


@app.route("/api/memory/add", methods=["POST"])
def api_memory_add():
    data   = request.get_json() or {}
    text   = data.get("text", "").strip()
    cat    = data.get("category", "general")
    if not text:
        return jsonify({"ok": False, "error": "חסר text"}), 400
    result = add_lesson(text, cat)
    return jsonify({"ok": True, "message": result})


@app.route("/api/memory/delete/<int:lesson_id>", methods=["DELETE"])
def api_memory_delete(lesson_id):
    result = forget_lesson(lesson_id)
    return jsonify({"ok": True, "message": result})


@app.route("/api/command", methods=["POST"])
def api_command():
    data   = request.get_json() or {}
    action = data.get("action", "")

    if action == "stop":
        jimmy_state["stop_requested"] = True
        return jsonify({"ok": True})
    if action == "force_analysis":
        jimmy_state["force_analysis"] = True
        return jsonify({"ok": True})
    if action == "shutdown":
        jimmy_state["shutdown_requested"] = True
        return jsonify({"ok": True, "message": "ג'ימי כובה..."})

    return jsonify({"ok": False, "error": f"פקודה לא מוכרת: {action}"})


# ──────────────────────────────────────────────
# Start
# ──────────────────────────────────────────────

def _tv_refresh_loop():
    """Thread רקע — מרענן screenshot מ-TradingView כל 30 שניות"""
    import time
    while True:
        try:
            from jimmy_tv import take_screenshot, health_check
            if health_check():
                b64, _ = take_screenshot("full")
                jimmy_state["screenshot_b64"] = b64
                jimmy_state["tv_connected"]   = True
            else:
                jimmy_state["tv_connected"] = False
        except Exception:
            pass
        time.sleep(30)


def start_web_server(port: int = 5000):
    # Web server thread
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
        daemon=True,
        name="jimmy-web"
    )
    t.start()
    # TV screenshot refresh thread
    threading.Thread(target=_tv_refresh_loop, daemon=True, name="tv-refresh").start()
    return t
