#!/usr/bin/env python3
"""
jimmy_server.py — ג'ימי 24/7 Server
════════════════════════════════════════
תמיד דלוק | צ'אט זמין בכל שעה | מסחר אוטומטי ב-KZ
גישה: http://localhost:5000
════════════════════════════════════════
"""

import os
import sys
import time
import json
import threading
import anthropic
from pathlib import Path
from datetime import datetime, timezone, timedelta

ISRAEL_TZ = timezone(timedelta(hours=3))
BASE_DIR  = Path(r"C:\Users\regev\New folder\ninjatrader-mcp")
DATA_DIR  = BASE_DIR / "data"
LOG_FILE  = DATA_DIR / "jimmy_log.txt"
BRAIN_FILE = DATA_DIR / "jimmy_brain.json"

# ── import web (Flask)
from jimmy_web      import start_web_server, jimmy_state, app as flask_app
from jimmy_research import start_research_scheduler, check_economic_calendar, get_daily_plan

# ── trading loop רץ כ-thread נפרד
_trading_thread: threading.Thread | None = None
_trading_active = False


def log(msg: str):
    now  = datetime.now(ISRAEL_TZ).strftime("%H:%M:%S")
    line = f"[{now}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def is_kill_zone() -> bool:
    now = datetime.now(ISRAEL_TZ)
    h, m = now.hour, now.minute
    return (h == 16 and m >= 30) or h == 17 or (h == 18 and m == 0)


def run_trading_loop():
    """מריץ את jimmy.py כ-thread — מתחיל בפתיחת KZ"""
    global _trading_active
    _trading_active = True
    log("🟢 Trading loop מתחיל (KZ פתוחה)")
    jimmy_state["status"] = "analyzing"
    try:
        # import כאן כדי שיעבוד גם אם jimmy.py לא ייטען מוקדם יותר
        import jimmy as jimmy_module
        jimmy_module.main()
    except Exception as e:
        log(f"❌ Trading loop שגיאה: {e}")
    finally:
        _trading_active = False
        jimmy_state["status"] = "waiting"
        log("🔴 Trading loop הסתיים")


def scheduler_loop():
    """
    לולאת 24/7 — בודקת כל דקה:
    - KZ פתחה? → הפעל trading thread
    - KZ נסגרה? → thread יסיים לבד
    """
    global _trading_thread

    log("📅 Scheduler פעיל — ג'ימי ידלק אוטומטית ב-16:30")

    while True:
        # בדוק אם נבקשה עצירה מלאה
        if jimmy_state.get("shutdown_requested"):
            log("🛑 Shutdown — ג'ימי כובה")
            break

        in_kz = is_kill_zone()

        if in_kz and (_trading_thread is None or not _trading_thread.is_alive()):
            # KZ פתוחה ואין thread — הפעל
            if not jimmy_state.get("stop_requested"):
                jimmy_state["stop_requested"] = False
                _trading_thread = threading.Thread(
                    target=run_trading_loop,
                    daemon=True,
                    name="jimmy-trading"
                )
                _trading_thread.start()

        # עדכן status ב-web
        if not in_kz:
            now = datetime.now(ISRAEL_TZ)
            if now.hour < 16:
                mins = (16 * 60 + 30) - (now.hour * 60 + now.minute)
                jimmy_state["status"] = "waiting"
                jimmy_state["next_kz"] = f"KZ ב-{16}:{30:02d} (עוד {mins} דק')"
            else:
                jimmy_state["status"] = "waiting"
                jimmy_state["next_kz"] = "KZ מחר ב-16:30"

        time.sleep(30)


def main():
    log("=" * 60)
    log("ג'ימי 24/7 Server מתחיל 🤖")
    log(f"Dashboard: http://localhost:5000")
    log("=" * 60)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log("❌ ANTHROPIC_API_KEY לא מוגדר!")
        log("הגדר: $env:ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    # הפעל Flask (צ'אט + dashboard) ב-background
    start_web_server(5000)
    log("🌐 Dashboard פעיל: http://localhost:5000")

    # בדוק לוח כלכלי בstartup (background thread כדי לא לעכב)
    def startup_calendar():
        try:
            events = check_economic_calendar()
            jimmy_state["today_events"] = events
            log(f"📅 לוח כלכלי: {events.get('summary','')}")
            if events.get("has_high_impact"):
                log(f"⚠️  HIGH IMPACT היום! Decision: {events.get('trading_decision')}")
        except Exception as e:
            log(f"לוח כלכלי: לא זמין ({e})")

    threading.Thread(target=startup_calendar, daemon=True, name="startup-calendar").start()

    # טען תכנית אם כבר הוכנה היום
    plan = get_daily_plan()
    if plan:
        jimmy_state["daily_plan"] = plan.get("plan", "")
        log("📋 תכנית סשן קיימת טעונה")

    # בדוק TradingView
    try:
        from jimmy_tv import health_check, _find_tv_tab
        tab = _find_tv_tab()
        log(f"📺 TV tab: {'נמצא' if tab else 'לא נמצא'}")
        tv_ok = health_check()
        jimmy_state["tv_connected"] = tv_ok
        log(f"{'✅' if tv_ok else '⚠️'} TradingView: {'מחובר' if tv_ok else 'לא זמין'}")
    except Exception as e:
        jimmy_state["tv_connected"] = False
        log(f"⚠️ TradingView startup error: {e}")

    # הפעל Scheduler
    sched = threading.Thread(target=scheduler_loop, daemon=True, name="jimmy-scheduler")
    sched.start()

    # הפעל research scheduler (מחקר בוקר ב-9:00)
    start_research_scheduler()
    log("🔍 Research scheduler פעיל — מחקר בוקר ב-09:00 כל יום")

    log("✅ ג'ימי דלוק 24/7 — צ'אט זמין תמיד, מסחר אוטומטי ב-KZ")
    log("Ctrl+C לכיבוי מלא")

    # שמור את ה-main thread חי
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        log("ג'ימי כובה (Ctrl+C) 👋")


if __name__ == "__main__":
    main()
