#!/usr/bin/env python3
"""
ג'ימי v2.0 — סוכן מסחר אוטונומי | MNQ ICT 2022 + Valtos + TradingView Vision
────────────────────────────────────────────────────────────────────────
גישה לדשבורד: http://localhost:5000
תחיל לבד ב-16:20 ישראל | בודק כל 2 דקות בKill Zone
────────────────────────────────────────────────────────────────────────
"""

import anthropic
import json
import os
import time
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Jimmy modules
from jimmy_tv       import get_full_tv_context, health_check as tv_health
from jimmy_web      import start_web_server, jimmy_state
from jimmy_learning import recorder as trade_recorder
from jimmy_research import start_research_scheduler

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

ISRAEL_TZ = timezone(timedelta(hours=3))
BASE_DIR   = Path(r"C:\Users\regev\New folder\ninjatrader-mcp")
DATA_DIR   = BASE_DIR / "data"

ORDERFLOW_FILE = DATA_DIR / "orderflow.json"
POSITION_FILE  = DATA_DIR / "position.json"
SIGNAL_FILE    = DATA_DIR / "trade_signal.json"
MONITOR_CFG    = DATA_DIR / "monitor_config.json"
SESSION_BIAS   = DATA_DIR / "session_bias.json"
JIMMY_LOG      = DATA_DIR / "jimmy_log.txt"
JIMMY_STATE    = DATA_DIR / "jimmy_state.json"

MIN_SL       = 15
MIN_RR       = 2.0
MAX_DAILY    = 2
LOOP_SEC     = 120
STALE_SEC    = 30
WEB_PORT     = 5000

# ──────────────────────────────────────────────
# System Prompt — ג'ימי הסוחר
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """אתה ג'ימי — סוחר MNQ עצמאי ומקצועי. ICT 2022 + Valtos Order Flow.
אתה לא מחכה לאישור. אתה מקבל החלטות לבד לפי הראיות בשטח.
אם התנאים מתקיימים — נכנסים. אם לא — יושבים בצד ומחכים.
סוחר טוב מחכה לסטאפ הנכון, לא מייצר אחד.

קיבלת:
1. נתוני OrderFlow מ-NT8 (CVD, delta, imbalances, Valtos score)
2. נתוני מחיר מ-TradingView (quote, Pine levels, bias labels)
3. צילום מסך — נתח ויזואלית את מבנה השוק
4. תכנית סשן שכתבת ב-16:00 עם triggers מוכנים
5. לוח כלכלי — אירועים שמשפיעים על NQ היום

## כללי ברזל (נלמדו מהפסדים):
1. כניסות רק 16:50–17:20 ישראל (Rule 22)
2. CVD < -5,000 = אסור LONG בכל מקרה (Rule 20)
3. Valtos score ≥ +3 = שקול LONG | ≤ -3 = שקול SHORT
4. SL מינימום 15 pts (Rule 1)
5. R/R מינימום 2.0 (Rule 5)
6. Capitulation: רק על סגירת בר מלאה, delta > +500 (Rule 17)
7. CDH = resistance קריטי, לא לתכנן TP מעליו (Rule 9)
8. HTF bias חייב לאשר (Rule 2) — bias BEARISH = רק SHORT
9. BSL sweep: בר חייב לסגור מתחת לרמה (Rule 18)
10. HIGH IMPACT EVENT during KZ = FLAT — אלא אם explicit approval

## ניתוח ויזואלי (מהצילום מסך):
- זהה trend direction ברור
- בדוק אם מחיר ב-FVG, OB, או בין רמות Pine
- ראה volume profile — איפה ה-POC
- בדוק אם יש structure break ברור

## פורמט תשובה (שורה אחת, חובה בדיוק):
FLAT | סיבה קצרה וספציפית
LONG | entry=X | sl=X | tp=X | rr=X.X
SHORT | entry=X | sl=X | tp=X | rr=X.X

אם FLAT — תסביר בדיוק מה חסר. לא "בכלל FLAT" — "FLAT כי CVD -3,200 לא עבר סף".
מחירים מדויקים. שורה אחת בלבד.
"""

# ──────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────

def log(msg: str):
    now  = datetime.now(ISRAEL_TZ).strftime("%H:%M:%S")
    line = f"[{now}] {msg}"
    print(line)
    with open(JIMMY_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json_nobom(path: Path, data: dict):
    path.write_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def get_state() -> dict:
    today = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")
    state = read_json(JIMMY_STATE) or {}
    if state.get("date") != today:
        state = {"date": today, "trades_today": 0, "last_signal": None, "signals": []}
        write_json_nobom(JIMMY_STATE, state)
    return state


def is_kill_zone() -> bool:
    now = datetime.now(ISRAEL_TZ)
    h, m = now.hour, now.minute
    return (h == 16 and m >= 30) or h == 17 or (h == 18 and m == 0)


def is_entry_window() -> bool:
    """Rule 22: כניסות רק 16:50–17:20"""
    now = datetime.now(ISRAEL_TZ)
    h, m = now.hour, now.minute
    return (h == 16 and m >= 50) or (h == 17 and m <= 20)


def is_nfp_friday() -> bool:
    """Rule 24: ראשון שישי בחודש"""
    now = datetime.now(ISRAEL_TZ)
    return now.weekday() == 4 and now.day <= 7


# ──────────────────────────────────────────────
# Valtos Score
# ──────────────────────────────────────────────

def calc_score(of: dict) -> tuple[int, float, list[str]]:
    bars    = of.get("bars", [])
    cvd     = sum(b.get("delta", 0) for b in bars)
    score   = 0
    reasons = []

    if cvd > 500:
        score += 1;  reasons.append(f"CVD +{cvd:.0f}")
    elif cvd < -500:
        score -= 1;  reasons.append(f"CVD {cvd:.0f}")

    cd = of.get("current_delta", 0)
    if cd > 0:
        score += 1;  reasons.append(f"delta +{cd}")
    elif cd < 0:
        score -= 1;  reasons.append(f"delta {cd}")

    for b in bars[:3]:
        if len(b.get("ask_imb", [])) >= 3:
            score += 1;  reasons.append(f"ASK imb x{len(b['ask_imb'])} @ {b.get('time','?')}")
        if len(b.get("bid_imb", [])) >= 3:
            score -= 1;  reasons.append(f"BID imb x{len(b['bid_imb'])} @ {b.get('time','?')}")

    return score, cvd, reasons


# ──────────────────────────────────────────────
# Signal Writer
# ──────────────────────────────────────────────

def send_signal(nt8_action: str, entry: float, sl: float, tp: float, rr: float, state: dict):
    signal = {
        "action":    nt8_action,
        "quantity":  1,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source":    "jimmy"
    }
    write_json_nobom(SIGNAL_FILE, signal)

    risk = abs(entry - sl)
    be   = round(entry + risk * 0.75, 2) if nt8_action == "BUY" else round(entry - risk * 0.75, 2)

    cfg = {
        "entry":      entry,
        "sl":         sl,
        "tp":         tp,
        "be_trigger": be,
        "direction":  "LONG" if nt8_action == "BUY" else "SHORT",
        "active":     True
    }
    write_json_nobom(MONITOR_CFG, cfg)

    # הפעל position_monitor.ps1 (Rule 23)
    monitor_path = str(BASE_DIR / "position_monitor.ps1")
    subprocess.Popen(
        ["powershell", "-NonInteractive", "-File", monitor_path],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )

    # עדכן state
    sig_record = {
        "action": nt8_action, "entry": entry, "sl": sl, "tp": tp, "rr": rr,
        "time": datetime.now(ISRAEL_TZ).strftime("%H:%M:%S")
    }
    state.setdefault("signals", []).append(sig_record)
    state["trades_today"] = state.get("trades_today", 0) + 1
    state["last_signal"]  = datetime.now(ISRAEL_TZ).isoformat()
    write_json_nobom(JIMMY_STATE, state)

    # עדכן web state
    jimmy_state["signals"]      = state["signals"]
    jimmy_state["trades_today"] = state["trades_today"]
    jimmy_state["status"]       = "signal_sent"

    log(f"✅ Signal: {nt8_action} @ {entry} | SL={sl} | TP={tp} | R/R={rr} | BE={be}")
    log(f"position_monitor.ps1 הופעל ✅")


# ──────────────────────────────────────────────
# Claude API — ניתוח + החלטה
# ──────────────────────────────────────────────

def ask_claude(of: dict, bias: dict | None, tv_ctx: dict,
               score: int, cvd: float, reasons: list) -> str:

    client   = anthropic.Anthropic()
    now_il   = datetime.now(ISRAEL_TZ).strftime("%H:%M")
    in_entry = is_entry_window()

    # טען לוח כלכלי ותכנית סשן
    today_events = {}
    daily_plan   = ""
    try:
        from jimmy_research import get_today_events, get_daily_plan as _get_plan
        today_events = get_today_events()
        plan_data    = _get_plan()
        daily_plan   = plan_data.get("plan", "") if plan_data else ""
    except Exception:
        pass

    summary = {
        "time_israel":         now_il,
        "in_entry_window":     in_entry,
        "price_nt8":           of.get("price"),
        "price_tv":            (tv_ctx.get("quote") or {}).get("close"),
        "tv_symbol":           (tv_ctx.get("state") or {}).get("symbol"),
        "tv_timeframe":        (tv_ctx.get("state") or {}).get("timeframe"),
        "cdh":                 of.get("cdh"),
        "cdl":                 of.get("cdl"),
        "pdh":                 of.get("pdh"),
        "pdl":                 of.get("pdl"),
        "current_delta":       of.get("current_delta"),
        "cvd_10bars":          round(cvd, 0),
        "valtos_score":        score,
        "score_reasons":       reasons,
        "htf_bias":            bias.get("htf_bias", "UNKNOWN") if bias else "UNKNOWN",
        "key_levels":          bias.get("key_levels", []) if bias else [],
        "tv_pine_labels":      tv_ctx.get("labels", []),
        "tv_pine_lines":       tv_ctx.get("lines", []),
        "economic_events":     today_events.get("summary", "לא נבדק"),
        "high_impact_today":   today_events.get("has_high_impact", False),
        "high_impact_kz":      today_events.get("during_kz", False),
        "econ_decision":       today_events.get("trading_decision", "NORMAL"),
        "session_plan":        daily_plan[:500] if daily_plan else "לא הוכנה תכנית",
        "last_3_bars": [
            {
                "time":      b["time"],
                "close":     b["c"],
                "delta":     b["delta"],
                "vol":       b["total_vol"],
                "bid_count": len(b.get("bid_imb", [])),
                "ask_count": len(b.get("ask_imb", []))
            }
            for b in of.get("bars", [])[:3]
        ]
    }

    # בנה content — טקסט + תמונה
    content = []

    if tv_ctx.get("screenshot_b64"):
        content.append({
            "type": "image",
            "source": {
                "type":       "base64",
                "media_type": "image/png",
                "data":       tv_ctx["screenshot_b64"]
            }
        })
        content.append({
            "type": "text",
            "text": f"צילום מסך הגרף מ-TradingView (עכשיו {now_il} ישראל)\nנתח ויזואלית ואז קרא את הנתונים:"
        })
    else:
        content.append({
            "type": "text",
            "text": f"TradingView לא זמין — עובד רק עם NT8 data:"
        })

    content.append({
        "type": "text",
        "text": json.dumps(summary, ensure_ascii=False, indent=2)
    })

    response = client.messages.create(
        model      = "claude-opus-4-8",
        max_tokens = 400,
        thinking   = {"type": "adaptive"},
        system     = SYSTEM_PROMPT,
        messages   = [{"role": "user", "content": content}]
    )

    for block in response.content:
        if block.type == "text":
            return block.text.strip()
    return "FLAT | no text response"


def parse_decision(decision: str) -> tuple[str, dict]:
    line = decision.strip().splitlines()[0]
    if line.startswith("LONG") or line.startswith("SHORT"):
        action = "LONG" if line.startswith("LONG") else "SHORT"
        params = {}
        for seg in line.split("|")[1:]:
            if "=" in seg:
                k, v = seg.split("=", 1)
                try:
                    params[k.strip()] = float(v.strip())
                except ValueError:
                    pass
        return action, params
    return "FLAT", {}


# ──────────────────────────────────────────────
# Main Loop
# ──────────────────────────────────────────────

def main():
    log("=" * 60)
    log("ג'ימי v2.0 — MNQ Trading Agent 🤖")
    log(f"Dashboard: http://localhost:{WEB_PORT}")
    log("=" * 60)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log("❌ ANTHROPIC_API_KEY לא מוגדר!")
        log("הגדר: $env:ANTHROPIC_API_KEY='sk-ant-...'")
        return

    if is_nfp_friday():
        log("⛔ NFP Friday — Rule 24: אסור לסחור")
        return

    # הפעל web dashboard ב-background
    start_web_server(WEB_PORT)
    log(f"🌐 Dashboard פעיל: http://localhost:{WEB_PORT}")

    # בדוק TradingView
    tv_available = tv_health()
    log(f"{'✅' if tv_available else '⚠️'} TradingView CDP: {'מחובר' if tv_available else 'לא זמין — עובד בלי TV vision'}")
    jimmy_state["tv_connected"] = tv_available

    consecutive_errors = 0

    while True:
        try:
            # בדוק פקודת עצירה מה-dashboard
            if jimmy_state.get("stop_requested"):
                log("⏹️ עצירה התקבלה מה-Dashboard")
                jimmy_state["status"] = "stopped"
                break

            now = datetime.now(ISRAEL_TZ)

            # ממתין ל-Kill Zone
            if not is_kill_zone():
                if now.hour >= 18:
                    log("KZ הסתיימה (18:00+). ג'ימי יוצא 👋")
                    jimmy_state["status"] = "stopped"
                    break
                kz_start = now.replace(hour=16, minute=30, second=0, microsecond=0)
                wait_sec = max(0, int((kz_start - now).total_seconds()))
                jimmy_state["status"] = "waiting"
                log(f"⏳ {now.strftime('%H:%M')} — KZ ב-16:30 (עוד {wait_sec//60} דק')")
                time.sleep(min(60, max(wait_sec, 1)))
                continue

            # בדוק מקסימום עסקאות
            state = get_state()
            if state["trades_today"] >= MAX_DAILY:
                log(f"⛔ מקסימום {MAX_DAILY} עסקאות היום")
                jimmy_state["status"] = "stopped"
                break

            # בדוק אם force analysis מה-dashboard
            force = jimmy_state.get("force_analysis", False)
            if force:
                jimmy_state["force_analysis"] = False

            # קרא orderflow
            of = read_json(ORDERFLOW_FILE)
            if not of:
                log("❌ orderflow.json לא נמצא — NT8 פועל?")
                time.sleep(30)
                continue

            # בדוק freshness (Rule 8)
            try:
                of_ts  = datetime.fromisoformat(of["timestamp"].replace("Z", "+00:00"))
                age    = (datetime.now(timezone.utc) - of_ts.astimezone(timezone.utc)).total_seconds()
                if age > STALE_SEC and not force:
                    log(f"⚠️ orderflow ישן {age:.0f}s — Rule 8: מדלג")
                    jimmy_state["status"] = "waiting"
                    time.sleep(15)
                    continue
            except Exception:
                pass

            # בדוק פוזיציה פתוחה
            pos = read_json(POSITION_FILE)
            if pos and pos.get("status") == "open":
                log(f"📊 פוזיציה: {pos.get('direction','?')} @ {pos.get('entry','?')}")
                jimmy_state["status"] = "waiting"
                time.sleep(30)
                continue

            # חשב Valtos score
            score, cvd, reasons = calc_score(of)
            log(f"📈 price={of.get('price')} | score={score:+d} | CVD={cvd:.0f} | δ={of.get('current_delta',0):+d}")

            # עדכן web state
            jimmy_state["orderflow"]    = of
            jimmy_state["score"]        = score
            jimmy_state["cvd"]          = cvd
            jimmy_state["current_price"]= of.get("price")
            jimmy_state["trades_today"] = state["trades_today"]
            jimmy_state["signals"]      = state.get("signals", [])

            # קרא TradingView (screenshot + נתונים)
            jimmy_state["status"] = "analyzing"
            log("📷 קורא TradingView...")
            tv_ctx = get_full_tv_context()

            # שמור screenshot ל-web state
            if tv_ctx.get("screenshot_b64"):
                jimmy_state["screenshot_b64"] = tv_ctx["screenshot_b64"]
                jimmy_state["tv_connected"]   = True
                log(f"📷 Screenshot: {tv_ctx.get('screenshot_path','')}")
            else:
                jimmy_state["tv_connected"] = False
                if tv_ctx.get("error"):
                    log(f"⚠️ TV: {tv_ctx['error']}")

            # קרא bias
            bias = read_json(SESSION_BIAS)
            htf  = bias.get("htf_bias", "UNKNOWN") if bias else "UNKNOWN"
            jimmy_state["htf_bias"] = htf

            # שלח לקלוד API
            log(f"🤖 שולח לקלוד | TV={'✅' if tv_ctx.get('available') else '❌'} | bias={htf}")
            decision = ask_claude(of, bias, tv_ctx, score, cvd, reasons)
            log(f"🤖 ג'ימי החליט: {decision}")

            jimmy_state["last_decision"] = decision
            jimmy_state["last_analysis"] = datetime.now(ISRAEL_TZ).isoformat()

            # פרס + בצע
            action, params = parse_decision(decision)

            if action in ("LONG", "SHORT"):
                entry = params.get("entry", of.get("price", 0))
                sl    = params.get("sl",    0)
                tp    = params.get("tp",    0)
                rr    = params.get("rr",    0)
                risk  = abs(entry - sl)

                if risk < MIN_SL:
                    log(f"⛔ SL קצר מדי: {risk:.1f} pts < {MIN_SL}")
                elif rr < MIN_RR:
                    log(f"⛔ R/R נמוך: {rr:.1f} < {MIN_RR}")
                else:
                    nt8_act = "BUY" if action == "LONG" else "SHORT"
                    send_signal(nt8_act, entry, sl, tp, rr, state)
                    # התחל מעקב ולמידה על העסקה
                    signal_rec = {"action": nt8_act, "entry": entry, "sl": sl, "tp": tp, "rr": rr}
                    trade_recorder.on_signal_sent(
                        signal_rec, of, tv_ctx.get("screenshot_path",""), decision
                    )
            else:
                jimmy_state["status"] = "waiting"

            consecutive_errors = 0
            time.sleep(LOOP_SEC)

        except KeyboardInterrupt:
            log("ג'ימי עצר (Ctrl+C) 👋")
            jimmy_state["status"] = "stopped"
            break
        except Exception as e:
            consecutive_errors += 1
            log(f"❌ שגיאה #{consecutive_errors}: {e}")
            if consecutive_errors >= 5:
                log("⛔ יותר מדי שגיאות")
                jimmy_state["status"] = "stopped"
                break
            jimmy_state["status"] = "waiting"
            time.sleep(30)


if __name__ == "__main__":
    main()
