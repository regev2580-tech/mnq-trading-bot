"""
sean_web.py — שון, מפקח פרויקט BeautyAI
Dashboard: http://localhost:5002
"""
import json
import os
import threading
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

import anthropic
import requests
from flask import Flask, jsonify, request, render_template_string

ISRAEL_TZ = timezone(timedelta(hours=3))
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
STATUS_FILE = DATA_DIR / "status.json"

# טעינת Supabase credentials — מenv vars או מ-.env של beautyai
def _load_env():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        env_path = BASE_DIR.parent / "beautyai" / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("SUPABASE_URL=") and not url:
                    url = line.split("=", 1)[1].strip()
                elif line.startswith("SUPABASE_ANON_KEY=") and not key:
                    key = line.split("=", 1)[1].strip()
    return url, key

SUPABASE_URL, SUPABASE_ANON_KEY = _load_env()
BEAUTYAI_URL = "http://localhost:3000"

app = Flask(__name__)
app.config["JSON_ENSURE_ASCII"] = False

chat_history: list[dict] = []


def sb_headers():
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }


def sb_get(table, params=None):
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=sb_headers(),
            params=params or {},
            timeout=10,
        )
        return r.json() if r.ok else []
    except Exception:
        return []


def get_whatsapp_status():
    """סטטוס חיבור הוואטסאפ הגלובלי של המערכת (instance אחד משותף לכל הקליניקות, ראה הערה ב-README)."""
    try:
        r = requests.get(f"{BEAUTYAI_URL}/api/whatsapp/status", timeout=5)
        return bool(r.json().get("connected")) if r.ok else False
    except Exception:
        return False


def fetch_all():
    businesses = sb_get("businesses", {
        "select": "id,name,owner_name,owner_phone,whatsapp_number,active,created_at,google_refresh_token,working_hours",
        "order": "created_at.desc",
    })
    treatments = sb_get("treatments", {"select": "id,business_id,name,duration_min,price,description,active"})
    treatments_per_biz: dict[str, int] = {}
    for t in (treatments or []):
        if t.get("active", True):
            bid = t.get("business_id")
            treatments_per_biz[bid] = treatments_per_biz.get(bid, 0) + 1

    whatsapp_connected = get_whatsapp_status()

    for b in (businesses or []):
        b["calendar_connected"] = bool(b.get("google_refresh_token"))
        b.pop("google_refresh_token", None)  # לא חושפים את הטוקן עצמו לדפדפן
        b["treatments_count"] = treatments_per_biz.get(b.get("id"), 0)
        b["whatsapp_connected"] = whatsapp_connected  # גלובלי כרגע — לא per-clinic

    unanswered = sb_get("unanswered_questions", {
        "select": "id,question,client_phone,created_at,answered,business_id",
        "answered": "eq.false",
        "order": "created_at.desc",
        "limit": "50",
    })
    appointments = sb_get("appointments", {
        "select": "id,client_name,client_phone,treatment_name,datetime,status,business_id",
        "order": "datetime.desc",
        "limit": "30",
    })
    conversations = sb_get("conversations", {
        "select": "business_id,client_phone,last_message_at",
        "order": "last_message_at.desc",
        "limit": "100",
    })
    knowledge = sb_get("business_knowledge", {
        "select": "id,question,answer,source,times_used,business_id",
        "order": "times_used.desc",
        "limit": "20",
    })

    # build business lookup
    biz_map = {b["id"]: b.get("name", "?") for b in (businesses or [])}

    # enrich unanswered with biz name
    for u in (unanswered or []):
        u["biz_name"] = biz_map.get(u.get("business_id"), "?")

    # enrich appointments with biz name
    for a in (appointments or []):
        a["biz_name"] = biz_map.get(a.get("business_id"), "?")

    # enrich knowledge with biz name
    for k in (knowledge or []):
        k["biz_name"] = biz_map.get(k.get("business_id"), "?")

    # conversations per business
    conv_per_biz: dict[str, int] = {}
    for c in (conversations or []):
        bid = c.get("business_id", "?")
        conv_per_biz[bid] = conv_per_biz.get(bid, 0) + 1

    return {
        "businesses": businesses or [],
        "treatments": treatments or [],
        "unanswered": unanswered or [],
        "appointments": appointments or [],
        "knowledge": knowledge or [],
        "conv_per_biz": conv_per_biz,
        "total_conversations": len(conversations or []),
    }


# ── ניטור מערכות — שון בודק כל 3 דקות שהכל חי ─────────────────────────────
HEALTH = {"checks": {}, "checked_at": None, "all_ok": None}
HEALTH_INTERVAL_SEC = 180

def run_health_check():
    checks = {}
    # 1. שרת beautyai
    try:
        r = requests.get(f"{BEAUTYAI_URL}/health", timeout=5)
        checks["server"] = {"ok": r.ok, "label": "שרת BeautyAI"}
    except Exception:
        checks["server"] = {"ok": False, "label": "שרת BeautyAI"}
    # 2. וואטסאפ (Green API דרך השרת)
    try:
        r = requests.get(f"{BEAUTYAI_URL}/api/whatsapp/status", timeout=8)
        connected = bool(r.json().get("connected")) if r.ok else False
        checks["whatsapp"] = {"ok": connected, "label": "וואטסאפ"}
    except Exception:
        checks["whatsapp"] = {"ok": False, "label": "וואטסאפ"}
    # 3. מסד נתונים Supabase
    biz = sb_get("businesses", {"select": "id", "limit": "1"})
    checks["database"] = {"ok": bool(biz), "label": "מסד נתונים"}

    HEALTH["checks"] = checks
    HEALTH["checked_at"] = datetime.now(ISRAEL_TZ).isoformat()
    HEALTH["all_ok"] = all(c["ok"] for c in checks.values())
    if not HEALTH["all_ok"]:
        bad = [c["label"] for c in checks.values() if not c["ok"]]
        write_status(f"⚠️ בעיה: {', '.join(bad)}")
    return HEALTH

def health_loop():
    while True:
        try:
            run_health_check()
        except Exception as e:
            print(f"[Health] שגיאה: {e}")
        time.sleep(HEALTH_INTERVAL_SEC)


def write_status(last_action="online"):
    d = {
        "name": "שון",
        "status": "online",
        "last_action": last_action,
        "timestamp": datetime.now(ISRAEL_TZ).isoformat(),
        "url": "http://localhost:5002",
    }
    STATUS_FILE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


SEAN_SYSTEM = """אתה שון — מפקח הפרויקט של BeautyAI.
אתה עובד ישירות עם רגב, היזם. הפרויקט: SaaS בוט וואטסאפ לקליניקות יופי בישראל.

תפקידך:
- לתת סקירות מצב: קליניקות רשומות, שאלות שלא נענו, תורים, פעילות שיחות
- לזהות דפוסים: שאלות חוזרות, קליניקות לא פעילות, נושאים שהבוט צריך ללמוד
- להמליץ על שיפורים (לא לבצע בעצמך — להציג ולהמליץ)
- לדווח כמו מנהל פרויקט מקצועי: קצר, ענייני, עם נתונים

ענה תמיד בעברית, בגוף ראשון. אתה מקצועי אך ידידותי.
"""


def build_sean_context() -> str:
    d = fetch_all()
    biz_lines = "\n".join(
        f"  • {b.get('name','?')} | {b.get('whatsapp_number','?')} | פעיל: {'כן' if b.get('active') else 'לא'}"
        for b in d["businesses"][:8]
    )
    unanswered_lines = "\n".join(
        f"  • [{u.get('biz_name','?')}] {u.get('question','?')[:80]}"
        for u in d["unanswered"][:5]
    )
    return f"""
מצב BeautyAI ({datetime.now(ISRAEL_TZ).strftime('%H:%M %d/%m/%Y')}):
- קליניקות רשומות: {len(d['businesses'])}
- שאלות פתוחות: {len(d['unanswered'])}
- שיחות במעקב: {d['total_conversations']}
- תורים: {len(d['appointments'])}

קליניקות:
{biz_lines or '  אין עדיין'}

שאלות פתוחות (5 אחרונות):
{unanswered_lines or '  אין — הכל מטופל!'}
"""


def sean_chat(user_message: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    context = build_sean_context()
    messages = [{"role": m["role"], "content": m["content"]} for m in chat_history[-10:]]
    messages.append({"role": "user", "content": f"[context]\n{context}\n\n[הודעה]\n{user_message}"})
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=SEAN_SYSTEM,
        messages=messages,
    )
    reply = response.content[0].text.strip()
    chat_history.append({"role": "user", "content": user_message})
    chat_history.append({"role": "assistant", "content": reply})
    write_status(f"ענה: {user_message[:40]}")
    return reply


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>שון — BeautyAI Manager</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;600;700;800&family=Frank+Ruhl+Libre:wght@700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#faf8f6;color:#241a26;font-family:'Heebo',sans-serif;height:100vh;display:flex;flex-direction:column;font-size:13px}
h1{font-family:'Frank Ruhl Libre',serif}
.header{background:#fff;border-bottom:1px solid #ece7ea;padding:10px 18px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.header h1{font-size:17px;font-weight:700}.header h1 span{color:#d6456f}
.badge{padding:4px 11px;border-radius:20px;font-size:11px;font-weight:600;background:#fbeff3;color:#d6456f}
.tabs{display:flex;gap:0;background:#fff;border-bottom:1px solid #ece7ea;padding:0 18px;flex-shrink:0}
.tab{padding:10px 16px;cursor:pointer;border-bottom:2px solid transparent;font-size:12px;font-weight:600;color:#8a8fa3;transition:.15s;white-space:nowrap}
.tab.active{color:#d6456f;border-bottom-color:#d6456f}
.tab:hover{color:#1c1f2e}
.tab .cnt{background:#d6456f;color:#fff;border-radius:10px;padding:1px 6px;font-size:10px;margin-right:5px}
.body{flex:1;overflow:hidden;display:flex;flex-direction:column}
.panel{display:none;flex:1;overflow-y:auto;padding:16px}
.panel.active{display:flex;flex-direction:column;gap:12px}
/* Stats row */
.stats{display:flex;gap:10px;flex-wrap:wrap}
.stat-card{background:#fff;border:1px solid #ece7ea;border-radius:10px;padding:14px 18px;flex:1;min-width:130px}
.stat-card .num{font-size:28px;font-weight:700;color:#d6456f}
.stat-card .lbl{font-size:11px;color:#8a8fa3;margin-top:2px}
/* Cards grid */
.cards{display:flex;flex-wrap:wrap;gap:10px}
.biz-card{background:#fff;border:1px solid #ece7ea;border-radius:10px;padding:14px;width:260px}
.biz-card .biz-name{font-weight:700;font-size:14px;margin-bottom:6px}
.biz-card .biz-row{display:flex;justify-content:space-between;color:#5b5f73;font-size:11px;margin-top:3px}
.active-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#22c55e;margin-left:5px}
.inactive-dot{background:#d1d5db}
/* Table */
table{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;border:1px solid #ece7ea}
th{background:#f9fafb;padding:9px 12px;text-align:right;font-size:11px;color:#8a8fa3;font-weight:600;border-bottom:1px solid #ece7ea}
td{padding:9px 12px;border-bottom:1px solid #f1f2f8;font-size:12px;color:#1c1f2e}
tr:last-child td{border-bottom:none}
tr:hover td{background:#fdf8fa}
.q-text{max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600}
.pill.open{background:#fbeff3;color:#d6456f}
.pill.done{background:#dcfce7;color:#16a34a}
.pill.confirmed{background:#dbeafe;color:#1d4ed8}
.pill.pending{background:#fef9c3;color:#a16207}
/* Chat */
.chat-wrap{flex:1;display:flex;flex-direction:column;overflow:hidden}
.chat-messages{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:8px;padding-bottom:8px}
.msg{max-width:76%;padding:9px 13px;border-radius:13px;font-size:13px;line-height:1.6;white-space:pre-wrap}
.msg.user{background:#d6456f;color:#fff;align-self:flex-end;border-radius:13px 13px 3px 13px}
.msg.sean{background:#fff;border:1px solid #ece7ea;align-self:flex-start;border-radius:13px 13px 13px 3px;color:#1c1f2e}
.msg.sean .who{font-size:10px;color:#d6456f;font-weight:700;margin-bottom:3px}
.chat-input-row{padding:10px 0 0;display:flex;gap:8px;flex-shrink:0}
.chat-input{flex:1;background:#fff;border:1px solid #ece7ea;border-radius:8px;color:#1c1f2e;padding:9px 12px;font-size:13px;outline:none;resize:none;font-family:inherit}
.send-btn{background:#d6456f;border:none;color:#fff;border-radius:8px;padding:9px 18px;cursor:pointer;font-weight:700;font-size:13px}
.send-btn:hover{background:#b23458}
.quick-btns{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:8px}
.qbtn{background:#fff;border:1px solid #ece7ea;color:#5b5f73;border-radius:14px;padding:4px 10px;font-size:11px;cursor:pointer}
.qbtn:hover{background:#fbeff3;color:#d6456f;border-color:#d6456f}
.section-title{font-size:11px;font-weight:700;color:#8a8fa3;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}
.empty{color:#8a8fa3;font-size:12px;text-align:center;padding:24px}
.biz-card{cursor:pointer;transition:.15s}
.biz-card:hover{border-color:#d6456f;box-shadow:0 2px 8px rgba(232,96,138,.12)}
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(28,31,46,.45);z-index:50;align-items:center;justify-content:center}
.modal-overlay.active{display:flex}
.modal-box{background:#fff;border-radius:14px;width:420px;max-width:92vw;max-height:86vh;overflow-y:auto;padding:20px}
.modal-box h2{font-size:16px;margin-bottom:14px;display:flex;align-items:center;gap:8px}
.modal-close{cursor:pointer;color:#8a8fa3;font-size:18px;margin-right:auto}
.check-row{display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid #f1f2f8;font-size:13px}
.check-row:last-child{border-bottom:none}
.check-row .lbl{color:#5b5f73}
.status-ok{color:#16a34a;font-weight:700;font-size:12px}
.status-bad{color:#d6456f;font-weight:700;font-size:12px}
.modal-link{display:inline-block;margin-top:4px;background:#d6456f;color:#fff;text-decoration:none;border-radius:7px;padding:5px 12px;font-size:11px;font-weight:600}
.modal-link.secondary{background:#fff;color:#5b5f73;border:1px solid #ece7ea}
.modal-section-title{font-size:11px;font-weight:700;color:#8a8fa3;text-transform:uppercase;letter-spacing:.5px;margin:16px 0 4px}
</style>
</head>
<body>
<div class="header">
  <h1><span>שון</span> · BeautyAI Manager</h1>
  <span class="badge" id="badge">טוען...</span>
</div>
<div class="tabs">
  <div class="tab active" onclick="switchTab('overview')">סקירה כללית</div>
  <div class="tab" onclick="switchTab('clinics')" id="tab-clinics">קליניקות</div>
  <div class="tab" onclick="switchTab('questions')" id="tab-questions">שאלות פתוחות</div>
  <div class="tab" onclick="switchTab('appointments')" id="tab-appointments">תורים</div>
  <div class="tab" onclick="switchTab('knowledge')" id="tab-knowledge">בסיס ידע</div>
  <div class="tab" onclick="switchTab('teach')">✏️ ניהול ידע</div>
  <div class="tab" onclick="switchTab('chat')">שיחה עם שון</div>
</div>
<div class="body">

<!-- OVERVIEW -->
<div class="panel active" id="panel-overview">
  <div id="health-strip" style="display:flex;gap:14px;flex-wrap:wrap;align-items:center;background:#fff;border:1px solid #ece7ea;border-radius:10px;padding:10px 16px">
    <span style="font-size:11px;font-weight:700;color:#8a8fa3;letter-spacing:.5px">🩺 ניטור מערכות</span>
    <span id="hs-items" style="display:flex;gap:14px;flex-wrap:wrap;font-size:12px">טוען...</span>
    <span id="hs-time" style="margin-right:auto;font-size:10px;color:#8a8fa3"></span>
  </div>
  <div class="stats" id="stats-row">
    <div class="stat-card"><div class="num" id="s-biz">—</div><div class="lbl">קליניקות רשומות</div></div>
    <div class="stat-card"><div class="num" id="s-open" style="color:#d6456f">—</div><div class="lbl">שאלות פתוחות</div></div>
    <div class="stat-card"><div class="num" id="s-appt" style="color:#1d4ed8">—</div><div class="lbl">תורים</div></div>
    <div class="stat-card"><div class="num" id="s-conv" style="color:#16a34a">—</div><div class="lbl">שיחות</div></div>
  </div>
  <div>
    <div class="section-title">קליניקות</div>
    <div class="cards" id="overview-clinics"></div>
  </div>
  <div>
    <div class="section-title">שאלות פתוחות אחרונות</div>
    <table id="overview-q">
      <thead><tr><th>קליניקה</th><th>שאלה</th><th>תאריך</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>
</div>

<!-- CLINICS -->
<div class="panel" id="panel-clinics">
  <div class="section-title">קליניקות רשומות</div>
  <div class="cards" id="clinics-cards"></div>
</div>

<!-- QUESTIONS -->
<div class="panel" id="panel-questions">
  <div class="section-title">שאלות שהבוט לא ידע לענות (פתוחות)</div>
  <table id="questions-table">
    <thead><tr><th>קליניקה</th><th>שאלה</th><th>לקוח</th><th>תאריך</th></tr></thead>
    <tbody></tbody>
  </table>
</div>

<!-- APPOINTMENTS -->
<div class="panel" id="panel-appointments">
  <div class="section-title">תורים</div>
  <table id="appointments-table">
    <thead><tr><th>קליניקה</th><th>לקוח</th><th>טיפול</th><th>תאריך</th><th>סטטוס</th></tr></thead>
    <tbody></tbody>
  </table>
</div>

<!-- KNOWLEDGE -->
<div class="panel" id="panel-knowledge">
  <div class="section-title">ידע שנצבר (נלמד מתשובות בעלי עסקים)</div>
  <table id="knowledge-table">
    <thead><tr><th>קליניקה</th><th>שאלה</th><th>תשובה</th><th>שימושים</th></tr></thead>
    <tbody></tbody>
  </table>
</div>

<!-- TEACH / KNOWLEDGE MANAGEMENT -->
<div class="panel" id="panel-teach">
  <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start">
    <!-- Add new -->
    <div style="background:#fff;border:1px solid #ece7ea;border-radius:10px;padding:16px;width:340px;flex-shrink:0">
      <div class="section-title" style="margin-bottom:10px">הוסף ידע חדש לקליניקה</div>
      <div style="margin-bottom:8px">
        <label style="font-size:11px;color:#8a8fa3;display:block;margin-bottom:3px">קליניקה</label>
        <select id="teach-biz" style="width:100%;border:1px solid #ece7ea;border-radius:6px;padding:7px 10px;font-size:13px;background:#fafbfd;color:#1c1f2e;outline:none">
          <option value="">— בחר קליניקה —</option>
        </select>
      </div>
      <div style="margin-bottom:8px">
        <label style="font-size:11px;color:#8a8fa3;display:block;margin-bottom:3px">שאלה</label>
        <input id="teach-q" type="text" placeholder="מה שעות הפתיחה?" style="width:100%;border:1px solid #ece7ea;border-radius:6px;padding:7px 10px;font-size:13px;background:#fafbfd;color:#1c1f2e;outline:none">
      </div>
      <div style="margin-bottom:10px">
        <label style="font-size:11px;color:#8a8fa3;display:block;margin-bottom:3px">תשובה</label>
        <textarea id="teach-a" rows="3" placeholder="אנחנו פתוחות א׳-ה׳ 09:00-20:00, שישי 09:00-14:00." style="width:100%;border:1px solid #ece7ea;border-radius:6px;padding:7px 10px;font-size:13px;background:#fafbfd;color:#1c1f2e;outline:none;resize:vertical;font-family:inherit"></textarea>
      </div>
      <button onclick="addKnowledge()" style="background:#d6456f;color:#fff;border:none;border-radius:8px;padding:9px 20px;font-size:13px;font-weight:700;cursor:pointer;width:100%">+ הוסף לבוט</button>
      <div id="teach-msg" style="margin-top:8px;font-size:12px;text-align:center;min-height:18px"></div>
    </div>
    <!-- Table -->
    <div style="flex:1;min-width:0">
      <div class="section-title" style="margin-bottom:6px">ידע קיים — ניתן לעריכה ומחיקה</div>
      <div style="margin-bottom:8px;display:flex;gap:8px;align-items:center">
        <label style="font-size:11px;color:#8a8fa3">סנן לפי קליניקה:</label>
        <select id="teach-filter" onchange="filterKnowledge()" style="border:1px solid #ece7ea;border-radius:6px;padding:5px 8px;font-size:12px;background:#fafbfd;color:#1c1f2e;outline:none">
          <option value="">כולן</option>
        </select>
      </div>
      <table id="teach-table" style="width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;border:1px solid #ece7ea">
        <thead><tr>
          <th style="background:#f9fafb;padding:9px 12px;text-align:right;font-size:11px;color:#8a8fa3;font-weight:600;border-bottom:1px solid #ece7ea">קליניקה</th>
          <th style="background:#f9fafb;padding:9px 12px;text-align:right;font-size:11px;color:#8a8fa3;font-weight:600;border-bottom:1px solid #ece7ea">שאלה</th>
          <th style="background:#f9fafb;padding:9px 12px;text-align:right;font-size:11px;color:#8a8fa3;font-weight:600;border-bottom:1px solid #ece7ea">תשובה</th>
          <th style="background:#f9fafb;padding:9px 12px;text-align:right;font-size:11px;color:#8a8fa3;font-weight:600;border-bottom:1px solid #ece7ea">מקור</th>
          <th style="background:#f9fafb;padding:9px 12px;text-align:right;font-size:11px;color:#8a8fa3;font-weight:600;border-bottom:1px solid #ece7ea"></th>
        </tr></thead>
        <tbody id="teach-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- CHAT -->
<div class="panel" id="panel-chat">
  <div class="chat-wrap">
    <div class="quick-btns">
      <button class="qbtn" onclick="sendQ('תסכם לי את מצב הפרויקט')">סיכום מצב</button>
      <button class="qbtn" onclick="sendQ('אלו שאלות חוזרות שהבוט לא יודע לענות?')">שאלות חוזרות</button>
      <button class="qbtn" onclick="sendQ('אלו קליניקות לא פעילות?')">קליניקות לא פעילות</button>
      <button class="qbtn" onclick="sendQ('מה אני צריך לשפר בבוט השבוע?')">המלצות שיפור</button>
    </div>
    <div class="chat-messages" id="chat-messages">
      <div class="msg sean"><div class="who">שון</div>שלום רגב! אני שון, מפקח הפרויקט שלך ב-BeautyAI.<br>אני מחובר לסופאבייס ורואה את כל הנתונים בזמן אמת.<br><br>מה תרצה לדעת?</div>
    </div>
    <div class="chat-input-row">
      <textarea class="chat-input" id="chat-input" rows="2" placeholder="שאל את שון..."
        onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChat();}"></textarea>
      <button class="send-btn" onclick="sendChat()">שלח</button>
    </div>
  </div>
</div>

</div>

<!-- CLINIC DETAIL MODAL -->
<div class="modal-overlay" id="clinic-modal" onclick="if(event.target===this) closeClinicModal()">
  <div class="modal-box" id="clinic-modal-box"></div>
</div>

<script>
let allData = {};

function switchTab(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('panel-'+name).classList.add('active');
  event.currentTarget.classList.add('active');
}

function fmt(iso) {
  if(!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('he-IL') + ' ' + d.toLocaleTimeString('he-IL',{hour:'2-digit',minute:'2-digit'});
}

function statusPill(s) {
  const map = {confirmed:'confirmed',pending:'pending',completed:'done',cancelled:'open'};
  return `<span class="pill ${map[s]||''}">${s||'?'}</span>`;
}

function renderData(d) {
  allData = d;
  const biz = d.businesses || [], uq = d.unanswered || [], appt = d.appointments || [], know = d.knowledge || [];

  // badge
  document.getElementById('badge').textContent = 'online';

  // tab counts
  const tabQ = document.getElementById('tab-questions');
  if(uq.length > 0) tabQ.innerHTML = `שאלות פתוחות <span class="cnt">${uq.length}</span>`;
  document.getElementById('tab-clinics').textContent = `קליניקות (${biz.length})`;
  document.getElementById('tab-appointments').textContent = `תורים (${appt.length})`;

  // stats
  document.getElementById('s-biz').textContent = biz.length;
  document.getElementById('s-open').textContent = uq.length;
  document.getElementById('s-appt').textContent = appt.length;
  document.getElementById('s-conv').textContent = d.total_conversations;

  // overview clinics
  const oc = document.getElementById('overview-clinics');
  oc.innerHTML = biz.length ? biz.map(b => bizCard(b, d.conv_per_biz)).join('') : '<div class="empty">אין קליניקות עדיין</div>';

  // clinics tab
  const cc = document.getElementById('clinics-cards');
  cc.innerHTML = biz.length ? biz.map(b => bizCard(b, d.conv_per_biz)).join('') : '<div class="empty">אין קליניקות עדיין</div>';

  // overview questions (top 5)
  const oqBody = document.querySelector('#overview-q tbody');
  oqBody.innerHTML = uq.slice(0,5).map(u => `
    <tr><td>${u.biz_name||'?'}</td>
    <td class="q-text" title="${u.question||''}">${u.question||'?'}</td>
    <td>${fmt(u.created_at)}</td></tr>`).join('') || '<tr><td colspan="3" class="empty">אין שאלות פתוחות</td></tr>';

  // questions tab
  const qtBody = document.querySelector('#questions-table tbody');
  qtBody.innerHTML = uq.map(u => `
    <tr><td>${u.biz_name||'?'}</td>
    <td class="q-text" title="${u.question||''}">${u.question||'?'}</td>
    <td>${u.client_phone||'?'}</td>
    <td>${fmt(u.created_at)}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">אין שאלות פתוחות!</td></tr>';

  // appointments tab
  const atBody = document.querySelector('#appointments-table tbody');
  atBody.innerHTML = appt.map(a => `
    <tr><td>${a.biz_name||'?'}</td>
    <td>${a.client_name||a.client_phone||'?'}</td>
    <td>${a.treatment_name||'?'}</td>
    <td>${fmt(a.datetime)}</td>
    <td>${statusPill(a.status)}</td></tr>`).join('') || '<tr><td colspan="5" class="empty">אין תורים</td></tr>';

  // knowledge tab
  const ktBody = document.querySelector('#knowledge-table tbody');
  ktBody.innerHTML = know.map(k => `
    <tr><td>${k.biz_name||'?'}</td>
    <td class="q-text" title="${k.question||''}">${k.question||'?'}</td>
    <td>${(k.answer||'?').slice(0,80)}</td>
    <td>${k.times_used||0}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">אין ידע עדיין</td></tr>';
}

function bizCard(b, convMap) {
  const active = b.active;
  const convs = convMap ? (convMap[b.id] || 0) : 0;
  const since = b.created_at ? new Date(b.created_at).toLocaleDateString('he-IL') : '?';
  return `<div class="biz-card" onclick="openClinicModal('${b.id}')">
    <div class="biz-name"><span class="${active?'active-dot':'inactive-dot'}"></span>${b.name||'?'}</div>
    <div class="biz-row"><span>בעלים:</span><span>${b.owner_name||'?'}</span></div>
    <div class="biz-row"><span>וואטסאפ:</span><span>${b.whatsapp_number||'?'}</span></div>
    <div class="biz-row"><span>שיחות:</span><span>${convs}</span></div>
    <div class="biz-row"><span>נרשם:</span><span>${since}</span></div>
  </div>`;
}

let clinicModalEditing = false;

function beautyaiBase() {
  return `${location.protocol}//${location.hostname}:3000`;
}

function openClinicModal(bizId) {
  clinicModalEditing = false;
  renderClinicModal(bizId);
  document.getElementById('clinic-modal').classList.add('active');
}

function closeClinicModal() {
  document.getElementById('clinic-modal').classList.remove('active');
}

function renderClinicModal(bizId) {
  const b = (allData.businesses || []).find(x => x.id === bizId);
  if (!b) return;
  const convs = (allData.conv_per_biz || {})[bizId] || 0;
  const openQ = (allData.unanswered || []).filter(u => u.business_id === bizId).length;
  const appts = (allData.appointments || []).filter(a => a.business_id === bizId).length;
  const know = (allData.knowledge || []).filter(k => k.business_id === bizId).length;
  const treats = (allData.treatments || []).filter(t => t.business_id === bizId);
  const since = b.created_at ? new Date(b.created_at).toLocaleDateString('he-IL') : '?';
  const wh = b.working_hours || {start:'09:00', end:'19:00'};

  const calRow = b.calendar_connected
    ? `<span class="status-ok">✅ מחובר</span>`
    : `<div><span class="status-bad">❌ לא מחובר</span><br>
        <a class="modal-link" href="${beautyaiBase()}/auth/google?businessId=${b.id}" target="_blank">חברי יומן גוגל</a></div>`;

  const waRow = b.whatsapp_connected
    ? `<span class="status-ok">✅ מחובר (גלובלי)</span>`
    : `<div><span class="status-bad">❌ לא מחובר</span><br>
        <a class="modal-link" href="${beautyaiBase()}/register.html?businessId=${b.id}&step=4" target="_blank">חברי / חברי מחדש וואטסאפ</a></div>`;

  const detailsBlock = clinicModalEditing ? `
    <div class="check-row"><span class="lbl">שם קליניקה</span><input id="ed-name" value="${b.name||''}" style="width:55%;border:1px solid #ece7ea;border-radius:6px;padding:4px 8px;font-size:12px"></div>
    <div class="check-row"><span class="lbl">בעלים</span><input id="ed-owner_name" value="${b.owner_name||''}" style="width:55%;border:1px solid #ece7ea;border-radius:6px;padding:4px 8px;font-size:12px"></div>
    <div class="check-row"><span class="lbl">טלפון בעלים</span><input id="ed-owner_phone" value="${b.owner_phone||''}" style="width:55%;border:1px solid #ece7ea;border-radius:6px;padding:4px 8px;font-size:12px"></div>
    <div class="check-row"><span class="lbl">מספר וואטסאפ</span><input id="ed-whatsapp_number" value="${b.whatsapp_number||''}" style="width:55%;border:1px solid #ece7ea;border-radius:6px;padding:4px 8px;font-size:12px"></div>
    <div class="check-row"><span class="lbl">שעות פעילות</span>
      <span><input id="ed-wh-start" value="${wh.start||'09:00'}" style="width:60px;border:1px solid #ece7ea;border-radius:6px;padding:4px 6px;font-size:12px">–
      <input id="ed-wh-end" value="${wh.end||'19:00'}" style="width:60px;border:1px solid #ece7ea;border-radius:6px;padding:4px 6px;font-size:12px"></span></div>
    <div class="check-row"><span class="lbl">פעיל</span><input id="ed-active" type="checkbox" ${b.active?'checked':''}></div>
    <div style="display:flex;gap:8px;margin-top:8px">
      <button class="modal-link" style="border:none" onclick="saveClinicEdit('${b.id}')">שמור</button>
      <button class="modal-link secondary" onclick="clinicModalEditing=false;renderClinicModal('${b.id}')">ביטול</button>
    </div>
  ` : `
    <div class="check-row"><span class="lbl">בעלים</span><span>${b.owner_name||'?'}</span></div>
    <div class="check-row"><span class="lbl">טלפון בעלים</span><span>${b.owner_phone||'—'}</span></div>
    <div class="check-row"><span class="lbl">מספר וואטסאפ</span><span>${b.whatsapp_number||'?'}</span></div>
    <div class="check-row"><span class="lbl">שעות פעילות</span><span>${wh.start||'?'}–${wh.end||'?'}</span></div>
    <div class="check-row"><span class="lbl">נרשם בתאריך</span><span>${since}</span></div>
    <button class="modal-link secondary" style="margin-top:6px" onclick="clinicModalEditing=true;renderClinicModal('${b.id}')">✏️ ערוך פרטים</button>
  `;

  const treatsRows = treats.map(t => `
    <div class="check-row" id="tr-${t.id}">
      <span class="lbl" contenteditable="true" id="trn-${t.id}" onblur="saveTreatmentEdit('${t.id}','${bizId}')" style="outline:none">${t.name||''}</span>
      <span style="display:flex;gap:6px;align-items:center">
        <span contenteditable="true" id="trd-${t.id}" onblur="saveTreatmentEdit('${t.id}','${bizId}')" style="outline:none;width:40px;display:inline-block">${t.duration_min||60}</span>ד׳
        <span contenteditable="true" id="trp-${t.id}" onblur="saveTreatmentEdit('${t.id}','${bizId}')" style="outline:none;width:45px;display:inline-block">${t.price||0}</span>₪
        <span onclick="deleteTreatment('${t.id}','${bizId}')" style="cursor:pointer;color:#d6456f">🗑</span>
      </span>
    </div>`).join('') || `<div class="check-row"><span class="lbl status-bad">⚠️ אין טיפולים מוגדרים</span></div>`;

  document.getElementById('clinic-modal-box').innerHTML = `
    <h2><span class="${b.active?'active-dot':'inactive-dot'}"></span>${b.name||'?'} <span class="modal-close" onclick="closeClinicModal()">✕</span></h2>
    ${detailsBlock}

    <div class="modal-section-title">חיבורים</div>
    <div class="check-row"><span class="lbl">וואטסאפ</span>${waRow}</div>
    <div class="check-row"><span class="lbl">יומן גוגל</span>${calRow}</div>

    <div class="modal-section-title">פעילות</div>
    <div class="check-row"><span class="lbl">שיחות פעילות</span><span>${convs}</span></div>
    <div class="check-row"><span class="lbl">תורים</span><span>${appts}</span></div>
    <div class="check-row"><span class="lbl">פריטי ידע</span><span>${know}</span></div>
    <div class="check-row"><span class="lbl">שאלות פתוחות</span><span>${openQ>0?`<span class="status-bad">${openQ}</span>`:'0'}</span></div>

    <div class="modal-section-title">טיפולים (${treats.length})</div>
    ${treatsRows}
    <div style="display:flex;gap:6px;margin-top:8px">
      <input id="nt-name-${bizId}" placeholder="שם טיפול" style="flex:1;border:1px solid #ece7ea;border-radius:6px;padding:5px 8px;font-size:12px">
      <input id="nt-dur-${bizId}" placeholder="דק'" style="width:48px;border:1px solid #ece7ea;border-radius:6px;padding:5px 6px;font-size:12px">
      <input id="nt-price-${bizId}" placeholder="₪" style="width:48px;border:1px solid #ece7ea;border-radius:6px;padding:5px 6px;font-size:12px">
      <button class="modal-link" style="border:none" onclick="addTreatmentFromModal('${bizId}')">+ הוסף</button>
    </div>
  `;
}

async function saveClinicEdit(bizId) {
  const payload = {
    name: document.getElementById('ed-name').value.trim(),
    owner_name: document.getElementById('ed-owner_name').value.trim(),
    owner_phone: document.getElementById('ed-owner_phone').value.trim(),
    whatsapp_number: document.getElementById('ed-whatsapp_number').value.trim(),
    working_hours_start: document.getElementById('ed-wh-start').value.trim(),
    working_hours_end: document.getElementById('ed-wh-end').value.trim(),
    active: document.getElementById('ed-active').checked,
  };
  try {
    await fetch('/api/business/' + bizId, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    clinicModalEditing = false;
    await loadData();
    renderClinicModal(bizId);
  } catch(e) { alert('שגיאת שמירה'); }
}

async function addTreatmentFromModal(bizId) {
  const name = document.getElementById('nt-name-'+bizId).value.trim();
  const duration_min = document.getElementById('nt-dur-'+bizId).value.trim();
  const price = document.getElementById('nt-price-'+bizId).value.trim();
  if (!name) return;
  try {
    await fetch('/api/treatments', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({business_id: bizId, name, duration_min, price})});
    await loadData();
    renderClinicModal(bizId);
  } catch(e) {}
}

async function saveTreatmentEdit(id, bizId) {
  const name = document.getElementById('trn-'+id)?.textContent.trim();
  const duration_min = document.getElementById('trd-'+id)?.textContent.trim();
  const price = document.getElementById('trp-'+id)?.textContent.trim();
  try {
    await fetch('/api/treatments/'+id, {method:'PUT', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name, duration_min: parseInt(duration_min)||60, price: parseInt(price)||0})});
    await loadData();
  } catch(e) {}
}

async function deleteTreatment(id, bizId) {
  if (!confirm('למחוק טיפול זה?')) return;
  try {
    await fetch('/api/treatments/'+id, {method:'DELETE'});
    await loadData();
    renderClinicModal(bizId);
  } catch(e) {}
}

async function loadData() {
  try {
    const d = await (await fetch('/api/data')).json();
    renderData(d);
  } catch(e){ document.getElementById('badge').textContent = 'שגיאת חיבור'; }
}

async function sendChat() {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if(!msg) return;
  input.value='';
  addMsg('user', msg);
  const tid = 'ty'+Date.now();
  addMsg('sean','...', tid);
  try {
    const r = await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});
    const d = await r.json();
    document.getElementById(tid)?.remove();
    addMsg('sean', d.reply||'שגיאה');
  } catch(e){
    document.getElementById(tid)?.remove();
    addMsg('sean','❌ שגיאת חיבור');
  }
}

function sendQ(msg){ document.getElementById('chat-input').value=msg; sendChat(); }

function addMsg(role, text, id) {
  const box = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'msg '+role;
  if(id) div.id = id;
  if(role==='sean') div.innerHTML = `<div class="who">שון</div>${text.replace(/\n/g,'<br>')}`;
  else div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

async function loadHealth() {
  try {
    const h = await (await fetch('/api/health')).json();
    const items = Object.values(h.checks || {}).map(c =>
      `<span style="display:inline-flex;align-items:center;gap:5px">
        <span style="width:8px;height:8px;border-radius:50%;background:${c.ok ? '#22c55e' : '#ef4444'};${c.ok ? '' : 'box-shadow:0 0 0 3px rgba(239,68,68,.18)'}"></span>
        <span style="color:${c.ok ? '#1c1f2e' : '#ef4444'};font-weight:${c.ok ? '500' : '700'}">${c.label}</span>
      </span>`).join('');
    document.getElementById('hs-items').innerHTML = items || 'אין נתונים';
    if (h.checked_at) {
      const t = new Date(h.checked_at);
      document.getElementById('hs-time').textContent = 'נבדק ' + t.toLocaleTimeString('he-IL', {hour:'2-digit',minute:'2-digit'});
    }
    document.getElementById('badge').textContent = h.all_ok ? 'online · הכל תקין' : '⚠️ יש בעיה';
    document.getElementById('badge').style.background = h.all_ok ? '#dcfce7' : '#fee2e2';
    document.getElementById('badge').style.color = h.all_ok ? '#16a34a' : '#dc2626';
  } catch(e) {}
}

loadData();
loadHealth();
setInterval(loadData, 15000);
setInterval(loadHealth, 60000);

// ── Knowledge management ──────────────────────────────────────────────────
let allKnowledge = [];

async function loadBusinessesForTeach() {
  try {
    const biz = await (await fetch('/api/businesses')).json();
    const sel = document.getElementById('teach-biz');
    const flt = document.getElementById('teach-filter');
    biz.forEach(b => {
      [sel, flt].forEach(el => {
        const o = document.createElement('option');
        o.value = b.id; o.textContent = b.name;
        el.appendChild(o);
      });
    });
  } catch(e){}
}

function renderKnowledgeTable(rows) {
  const tbody = document.getElementById('teach-tbody');
  if(!rows || !rows.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty">אין ידע עדיין — הוסף את הראשון!</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(k => `
    <tr id="kr-${k.id}">
      <td style="font-size:12px;padding:9px 12px;border-bottom:1px solid #f1f2f8;white-space:nowrap">${k.biz_name||'?'}</td>
      <td style="font-size:12px;padding:9px 12px;border-bottom:1px solid #f1f2f8;max-width:180px">
        <div contenteditable="true" id="kq-${k.id}" style="outline:none;cursor:text" onblur="saveEdit('${k.id}')">${k.question||''}</div>
      </td>
      <td style="font-size:12px;padding:9px 12px;border-bottom:1px solid #f1f2f8;max-width:220px">
        <div contenteditable="true" id="ka-${k.id}" style="outline:none;cursor:text" onblur="saveEdit('${k.id}')">${k.answer||''}</div>
      </td>
      <td style="font-size:12px;padding:9px 12px;border-bottom:1px solid #f1f2f8;white-space:nowrap">
        <span class="pill ${k.source==='owner'?'confirmed':'pending'}">${k.source==='owner'?'בעלת עסק':'ידני'}</span>
      </td>
      <td style="padding:9px 12px;border-bottom:1px solid #f1f2f8">
        <button onclick="deleteKnowledge('${k.id}')" style="background:none;border:1px solid #fca5a5;color:#ef4444;border-radius:6px;padding:3px 8px;cursor:pointer;font-size:11px">מחק</button>
      </td>
    </tr>`).join('');
}

function filterKnowledge() {
  const flt = document.getElementById('teach-filter').value;
  const rows = flt ? allKnowledge.filter(k => k.business_id === flt) : allKnowledge;
  renderKnowledgeTable(rows);
}

async function addKnowledge() {
  const biz = document.getElementById('teach-biz').value;
  const q = document.getElementById('teach-q').value.trim();
  const a = document.getElementById('teach-a').value.trim();
  const msg = document.getElementById('teach-msg');
  if(!biz || !q || !a) { msg.style.color='#d6456f'; msg.textContent='חסרים שדות'; return; }
  msg.style.color='#8a8fa3'; msg.textContent='שומר...';
  try {
    const r = await fetch('/api/knowledge',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({business_id:biz,question:q,answer:a})});
    const d = await r.json();
    if(d.ok) {
      msg.style.color='#16a34a'; msg.textContent='✅ נוסף בהצלחה!';
      document.getElementById('teach-q').value='';
      document.getElementById('teach-a').value='';
      loadData();
    } else { msg.style.color='#d6456f'; msg.textContent='❌ '+JSON.stringify(d.error); }
  } catch(e){ msg.style.color='#d6456f'; msg.textContent='❌ שגיאת רשת'; }
}

async function saveEdit(id) {
  const q = document.getElementById('kq-'+id)?.textContent.trim();
  const a = document.getElementById('ka-'+id)?.textContent.trim();
  if(!q || !a) return;
  try {
    await fetch('/api/knowledge/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,answer:a})});
  } catch(e){}
}

async function deleteKnowledge(id) {
  if(!confirm('למחוק ידע זה?')) return;
  try {
    await fetch('/api/knowledge/'+id,{method:'DELETE'});
    document.getElementById('kr-'+id)?.remove();
  } catch(e){}
}

// hook knowledge into renderData
const _origRender = renderData;
window.renderData = function(d) {
  _origRender(d);
  allKnowledge = d.knowledge || [];
  // update knowledge tab count
  const tk = document.getElementById('tab-knowledge');
  if(tk) tk.textContent = `בסיס ידע (${allKnowledge.length})`;
  filterKnowledge();
};

loadBusinessesForTeach();
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/data")
def api_data():
    return jsonify(fetch_all())


@app.route("/api/status")
def api_status():
    d = fetch_all()
    return jsonify({
        "name": "שון",
        "status": "online",
        "last_action": f"{len(d['businesses'])} קליניקות | {len(d['unanswered'])} שאלות פתוחות",
        "timestamp": datetime.now(ISRAEL_TZ).isoformat(),
        "url": "http://localhost:5002",
    })


@app.route("/api/health")
def api_health():
    if HEALTH["checked_at"] is None:
        run_health_check()
    return jsonify(HEALTH)


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"reply": "?"}), 400
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return jsonify({"reply": "❌ ANTHROPIC_API_KEY לא מוגדר"}), 500
    try:
        reply = sean_chat(message)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": f"❌ שגיאה: {e}"}), 500


# ── Knowledge CRUD ────────────────────────────────────────────────────────────

@app.route("/api/knowledge", methods=["POST"])
def api_knowledge_add():
    """הוסף ידע חדש לקליניקה ספציפית."""
    body = request.get_json() or {}
    business_id = body.get("business_id", "").strip()
    question = body.get("question", "").strip()
    answer = body.get("answer", "").strip()
    if not all([business_id, question, answer]):
        return jsonify({"error": "חסרים שדות"}), 400
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/business_knowledge",
            headers={**sb_headers(), "Prefer": "return=representation"},
            json={"business_id": business_id, "question": question, "answer": answer,
                  "source": "manual", "approved": True, "times_used": 0},
            timeout=10,
        )
        if r.ok:
            write_status(f"נוסף ידע לקליניקה {business_id[:8]}")
            return jsonify({"ok": True, "row": r.json()[0] if r.json() else {}})
        return jsonify({"error": r.text}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/knowledge/<row_id>", methods=["PUT"])
def api_knowledge_edit(row_id):
    """עדכן שאלה/תשובה קיימת."""
    body = request.get_json() or {}
    patch = {k: body[k] for k in ("question", "answer") if k in body}
    if not patch:
        return jsonify({"error": "אין מה לעדכן"}), 400
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/business_knowledge",
            headers={**sb_headers(), "Prefer": "return=representation"},
            params={"id": f"eq.{row_id}"},
            json=patch,
            timeout=10,
        )
        return jsonify({"ok": r.ok, "status": r.status_code})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/knowledge/<row_id>", methods=["DELETE"])
def api_knowledge_delete(row_id):
    """מחק ידע לפי id."""
    try:
        r = requests.delete(
            f"{SUPABASE_URL}/rest/v1/business_knowledge",
            headers=sb_headers(),
            params={"id": f"eq.{row_id}"},
            timeout=10,
        )
        write_status(f"נמחק ידע {row_id[:8]}")
        return jsonify({"ok": r.ok})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/businesses")
def api_businesses():
    """רשימת קליניקות בלבד — לטופס הוספת ידע."""
    biz = sb_get("businesses", {"select": "id,name", "order": "name.asc"})
    return jsonify(biz or [])


# ── Business edit ────────────────────────────────────────────────────────────

@app.route("/api/business/<biz_id>", methods=["PUT"])
def api_business_edit(biz_id):
    """עריכת פרטי קליניקה מהדשבורד הניהולי."""
    body = request.get_json() or {}
    allowed = ("name", "owner_name", "owner_phone", "whatsapp_number", "active")
    patch = {k: body[k] for k in allowed if k in body}
    if "working_hours_start" in body or "working_hours_end" in body:
        patch["working_hours"] = {
            "start": body.get("working_hours_start", "09:00"),
            "end": body.get("working_hours_end", "19:00"),
        }
    if not patch:
        return jsonify({"error": "אין מה לעדכן"}), 400
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/businesses",
            headers={**sb_headers(), "Prefer": "return=representation"},
            params={"id": f"eq.{biz_id}"},
            json=patch,
            timeout=10,
        )
        write_status(f"עודכנו פרטי קליניקה {biz_id[:8]}")
        return jsonify({"ok": r.ok, "status": r.status_code})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Treatments CRUD ───────────────────────────────────────────────────────────

@app.route("/api/treatments", methods=["POST"])
def api_treatment_add():
    body = request.get_json() or {}
    business_id = body.get("business_id", "").strip()
    name = body.get("name", "").strip()
    if not business_id or not name:
        return jsonify({"error": "חסרים שדות"}), 400
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/treatments",
            headers={**sb_headers(), "Prefer": "return=representation"},
            json={
                "business_id": business_id,
                "name": name,
                "duration_min": int(body.get("duration_min") or 60),
                "price": int(body.get("price") or 0),
                "description": body.get("description") or None,
                "active": True,
            },
            timeout=10,
        )
        if r.ok:
            write_status(f"נוסף טיפול לקליניקה {business_id[:8]}")
            return jsonify({"ok": True, "row": r.json()[0] if r.json() else {}})
        return jsonify({"error": r.text}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/treatments/<row_id>", methods=["PUT"])
def api_treatment_edit(row_id):
    body = request.get_json() or {}
    patch = {k: body[k] for k in ("name", "duration_min", "price", "description", "active") if k in body}
    if not patch:
        return jsonify({"error": "אין מה לעדכן"}), 400
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/treatments",
            headers={**sb_headers(), "Prefer": "return=representation"},
            params={"id": f"eq.{row_id}"},
            json=patch,
            timeout=10,
        )
        return jsonify({"ok": r.ok, "status": r.status_code})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/treatments/<row_id>", methods=["DELETE"])
def api_treatment_delete(row_id):
    try:
        r = requests.delete(
            f"{SUPABASE_URL}/rest/v1/treatments",
            headers=sb_headers(),
            params={"id": f"eq.{row_id}"},
            timeout=10,
        )
        write_status(f"נמחק טיפול {row_id[:8]}")
        return jsonify({"ok": r.ok})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    write_status("מופעל")
    threading.Thread(target=health_loop, daemon=True).start()
    print("💄 שון — BeautyAI Manager")
    print("🌐 http://localhost:5002")
    print(f"🩺 ניטור מערכות פעיל — בדיקה כל {HEALTH_INTERVAL_SEC // 60} דקות")
    app.run(host="0.0.0.0", port=5002, debug=False, use_reloader=False)
