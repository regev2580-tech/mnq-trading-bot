"""
teach_jimmy_history.py — מלמד את ג'ימי את כל היסטוריית העסקאות
הרץ פעם אחת: python teach_jimmy_history.py
"""

import os, json, anthropic
from pathlib import Path
from datetime import datetime, timezone, timedelta

ISRAEL_TZ = timezone(timedelta(hours=3))
DATA_DIR  = Path(r"C:\Users\regev\New folder\ninjatrader-mcp\data")

# ── כל היסטוריית העסקאות ──
ALL_TRADES_TEXT = """
═══════════════════════════════════════════════════
  היסטוריית עסקאות מלאה — ג'ימי לומד מהעבר
═══════════════════════════════════════════════════

== חשבון EVAL1 (ישן) — 2026-05-21 עד 2026-05-22 ==

T1: 2026-05-21 | SHORT | Entry 29,399.5 | Exit 29,260.5 | +139 pts | WIN (+3.5R)
  → ICT sweep מתחת 5-bar low → SL מתחת low → TP ב-structural high = מושלם
  → לקח: HTF alignment מלא + ICT sequence = WIN

T2: 2026-05-21 | SHORT | Entry 29,257 | Exit 29,285 | -28 pts | LOSS (-1R)
  → נכנסתי ישר אחרי T1 בלי לחכות לסטאפ חדש
  → לקח: אחרי WIN — לחכות לסטאפ חדש, לא לחפש מיד

T3: 2026-05-21 | LONG | Entry 29,270 | Exit 29,275 | +5 pts | BE
  → כניסה ללא candle close confirmation
  → לקח: כניסה תוך כדי בר = BE במקרה הטוב

T4: 2026-05-22 | SHORT | Entry 29,665 | Exit 29,712.5 | -47.5 pts | LOSS (-1R)
  → SL בתוך liquidity zone במקום מעל swing high
  → לקח: SL חייב להיות מעל/מתחת swing — לא בתוך האזור

T5: 2026-05-22 | LONG | Entry 29,577.5 | Exit 29,537.5 | -40 pts | LOSS (-1R)
  → כניסה אחרי 2 הפסדים ביום — Rule 3-losses
  → לקח: אחרי 2 הפסדים — עצור. לא משנה כמה טוב הסטאפ נראה

T6: 2026-05-22 | SHORT | Entry 29,628 | Exit 29,670 | -42 pts | LOSS (-1R)
  → כניסה ללא candle close + ה-3 ביום
  → לקח: כלל ברזל — מקסימום 2 עסקאות ביום

== חשבון LUCID2 — 2026-05-25 ==

T1: 2026-05-25 | LONG | 3 contracts | Entry 29,948 | SL 29,932.5 | Exit SL | -15.5 pts | -$93 | LOSS
  → כניסה ב-Kill Zone ללא HTF confirmation מלא
  → מה שפספסנו: MTF alignment מלא היה מראה TP ב-29,993 (נפגע!)
  → לקח: ניתוח MTF לפני KZ — לא תוך כדי

== חשבון CLAUDE1 (אוטומציה) — 16 עסקאות ==

-- 2026-05-27 (3 הפסדים ביום) --
T1-T3: הפסדים רצופים | Score גבוה אבל HTF לא אישר
  → orderflow score ≥3 ללא HTF = שלושה הפסדים
  → כלל 2 נולד כאן: HTF חייב לאשר

-- 2026-05-28 --
T3 (CLAUDE): LONG @ 29,981.25 | יצא ידנית @ 29,963 | -18 pts | LOSS
  → המשתמש כיבה ClaudeStrategy → missed 265 pts (29,920→30,185!)
  → לקח: לא לכבות ClaudeStrategy — רק לשנות SL/TP

T4 (CLAUDE): LONG @ 30,150 | יצא @ 30,117 | -33 pts | LOSS
  → Capitulation Rule: bar 17:25 delta -963 + bar 17:30 delta +1,364
  → יציאה על CDH rejection נכונה

T5 (CLAUDE): SHORT שגגה @ 30,128.5 → SELL כשFLAT פתח שורט!
  → position.json היה stale (>30 שניות)
  → לקח: stale data = לא נכנסים. Rule 8 נולד כאן

-- 2026-06-01 (ICT AMD Pattern) --
T1: LONG יציאה מוקדמת | היה רווחי אם נשמר
T4: LONG יציאה מוקדמת | היה רווחי אם נשמר
  → לקח: SL מבני = גבול אחד. לא יוצאים מוקדם

T5: LONG @ 30,337 | יצא @ 30,379 | +43 pts | WIN (+$86)
  → Capitulation: bar 16:15 delta -4,051 → bar 16:30 delta +1,827
  → AMD Pattern: Manipulation spike → Distribution down → כניסה LONG
  → יציאה: trigger מחיר ברור (מתחת 30,385)
  → לקח: הגדר trigger מחיר לפני הכניסה — לא תוך כדי

-- 2026-06-02 (NY AM + PM) --
T1 (CDH breakout retest): LONG @ 30,620 | SL @ 30,609 | -11 pts | LOSS
  → בר לא סגר מעל CDH לפני הכניסה
  → לקח: CDH retest = רק אחרי בר סגור מעל CDH + pullback נקי

T2 (Capitulation שגוי): BUY @ 30,615 | יצא -29 pts | LOSS
  → delta +590 בדקה 1 של הבר = FALSE capitulation
  → בסגירה: delta -4,828 → שוק לא הפך
  → לקח: Capitulation רק על סגירת בר מלאה עם delta > +500

T3 (BSL sweep): SHORT @ 30,698 | SL @ 30,703 | -21 pts | LOSS
  → מחיר עשה high חדש אחרי ה"sweep" = breakout, לא reversal
  → ה-CDH החדש 30,702.5 אישר continuation
  → לקח: BSL sweep → בר חייב לסגור מתחת לרמה כדי שיהיה reversal

סה"כ יום: -61 pts (-$122)

-- 2026-06-03 (Free Fall) --
0 עסקאות (FLAT נכון!)
  → CDH spike 30,807 → delta -1,031 → Free fall -7,988 → CDL sweep 30,495 (-312 pts)
  → CVD נשאר -8,000+ — כל bounce נמכר
  → SHORT שפוספס: bar 16:35 סגר 30,714 | delta -1,031 | SL מעל bar high 30,737 = 23 pts | R/R 9:1
  → פספסתי כי חישבתי SL מעל CDH (93 pts) במקום מעל הבר
  → לקח: SL = מעל bar high, לא מעל CDH כשיש rejection ברור

-- 2026-06-04 (Timing Missed) --
  → Wakeup ב-17:17 במקום 17:15 → מחיר עלה 22 pts → R/R ירד מ-2.72 ל-1.63 → missed
  → לקח: Rule 22 — 45 שניות לפני סגירת בר קריטי

-- 2026-06-08 (Momentum Day) --
  → CVD +5,132 | שוק עלה ברציפות בלי pullback עמוק
  → חיכיתי ל-OTE (pullback עמוק) שלא הגיע
  → BUY "executed" אבל position=flat → NT8 לא ביצע
  → לקח: CVD +3,000+ = Momentum Mode — אין pullbacks עמוקים, כניסה על כל דיפ קטן
  → לקח: לאחר signal — לבדוק position.json תוך 30 שניות

-- 2026-06-10 (CDH Rejection T15) --
T15: SHORT @ 29,028.75 | SL 29,174.75 | TP 28,610.25 | R/R 4.14
  → Bar 16:55: CDH rejection | סגר 29,029 | delta -1,863 | vol 60K [OK] סטאפ נכון
  → מחיר עלה ל-29,256 — 81 pts מעל SL!
  → SL=0 (לא נשמר בNT8) → Sim שרד במזל, סגר ב-23:00 ברווח
  → בחשבון אמיתי = הפסד -146 pts
  → לקח: position_monitor.ps1 חובה. SL=0 = לא סוחרים

== סיכום סטטיסטי כולל ==
EVAL1: 1W / 1BE / 4L | net: -13.5 pts
LUCID2: 0W / 0BE / 1L | net: -15.5 pts (-$93)
CLAUDE1: 3W / 13L | Win Rate 23% | avg WIN +25 pts | avg LOSS -19.5 pts | P.F. 0.39

== 3 הסיבות העיקריות להפסדים ==
1. כניסות לפני סגירת בר (T3,T7,T8,T9,T10) — 5 הפסדים
2. CVD שלילי = נגד momentum (T12,T13,T10) — 3 הפסדים
3. Over-trading (10 עסקאות ב-2 ימים) — spiral הפסדים

== מה עובד (100% win rate) ==
T1(EVAL), T5(CLAUDE), T15(כיוון נכון):
→ HTF מאושר + CVD חיובי/ניטרלי + בר סגור + SL מבני = WIN בכל פעם

== 28 כללי ברזל שנולדו מהפסדים ==
Rule 1: SL מינימום 15 pts
Rule 2: HTF חייב לאשר
Rule 3: Timestamp = Get-Date (לא replay)
Rule 4: לחכות לסגירת נר
Rule 5: לא נגד daily trend ללא reversal ברור
Rule 6: BE ב-1R (0.75R ביום volatile)
Rule 7: לא לכבות ClaudeStrategy — רק לשנות SL/TP
Rule 8: position.json >30s stale = לא נכנסים
Rule 9: CDH = resistance קריטי — לסגור חצי ב-CDH
Rule 10: SELL = סגירת LONG בלבד (SHORT = action "SHORT")
Rule 11: ניטור כל 60 שניות לפני כניסה
Rule 12: SL מבני = גבול אחד — לא יוצאים מוקדם
Rule 13: Capitulation absorption: delta > +500 (לא רק > 0)
Rule 14: BUY = market order (לא limit)
Rule 15: יציאה = trigger מחיר ברור לפני הכניסה
Rule 16: NT8 sl:0 = SL לא הוגדר — לנהל ידנית
Rule 17: Capitulation = סגירת בר מלאה בלבד
Rule 18: BSL sweep → בר חייב לסגור מתחת לרמה
Rule 19: Cron delay = עד 60 שניות — לנטר ידנית ברמות קריטיות
Rule 20: CVD < -5,000 = NO LONG בשום מקרה
Rule 21: SHORT trigger מוכן מראש לפני KZ
Rule 22: KZ AM: כניסות רק 16:50–17:20 (לא 16:30!)
Rule 23: position_monitor.ps1 חובה עם כל signal
Rule 24: NFP Friday = אסור ללא אישור
Rule 25: Wakeup 45 שניות לסגירות בר קריטיות
Rule 26: לאחר signal — בדוק position.json תוך 30 שניות
Rule 27: CVD +3,000+ = Momentum Mode (לא חכה לOTE)
Rule 28: Sim101 סוגר ב-23:00 — SL=0 = מזל, לא ניהול
"""

def teach_jimmy():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY לא מוגדר")
        return

    client = anthropic.Anthropic(api_key=api_key)
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8','utf8'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print("=== מלמד את גימי את כל ההיסטוריה ===")
    print("=" * 60)

    # ── שלב 1: ניתוח מעמיק של כל ההיסטוריה ──
    prompt = f"""אתה ג'ימי — סוחר MNQ בשיטת ICT 2022 + Valtos Order Flow.
קיבלת את כל היסטוריית העסקאות שלך עד היום.
למד אותה לעומק וחלץ לקחים מעשיים שישפרו את ביצועיך.

{ALL_TRADES_TEXT}

נתח את כל ההיסטוריה וענה בפורמט הזה בדיוק.
כתוב 20 לקחים ממוקדים ומעשיים:

LESSON_1: [לקח מדויק ומספרי אם אפשר]
LESSON_2: [לקח מדויק]
...
LESSON_20: [לקח מדויק]

PATTERN_WIN: [מה משותף לכל הניצחונות — 2-3 משפטים]
PATTERN_LOSS: [מה משותף לכל ההפסדים — 2-3 משפטים]
BIGGEST_INSIGHT: [התובנה הכי חשובה מכל ההיסטוריה — משפט אחד]
JIMMY_RULE: [כלל אחד שג'ימי צריך לפעול לפיו שלא מופיע ב-28 הכללים]

ענה בעברית. לקחים קצרים ומדויקים — לא כלליים.
"""

    print("[>>] שולח לקלוד Opus לניתוח מעמיק...")
    response = client.messages.create(
        model      = "claude-opus-4-8",
        max_tokens = 2000,
        thinking   = {"type": "adaptive"},
        messages   = [{"role": "user", "content": prompt}]
    )

    analysis = next((b.text for b in response.content if b.type == "text"), "")
    print("[OK] ניתוח התקבל")
    print()
    print(analysis)
    print()

    # ── שלב 2: שמור לזיכרון של ג'ימי ──
    BRAIN_FILE = DATA_DIR / "jimmy_brain.json"
    try:
        brain = json.loads(BRAIN_FILE.read_text(encoding="utf-8"))
    except Exception:
        brain = {"lessons": [], "rules_override": [], "trade_notes": []}

    lessons_added = 0
    for line in analysis.split("\n"):
        line = line.strip()
        for prefix in [f"LESSON_{i}:" for i in range(1, 21)]:
            if line.startswith(prefix):
                text = line.split(":", 1)[1].strip()
                if text and len(text) > 10:
                    brain["lessons"].append({
                        "id":       len(brain["lessons"]) + 1,
                        "text":     text,
                        "category": "historical_trade",
                        "date":     datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d %H:%M"),
                    })
                    lessons_added += 1

    # שמור pattern insights
    for prefix in ["PATTERN_WIN:", "PATTERN_LOSS:", "BIGGEST_INSIGHT:", "JIMMY_RULE:"]:
        for line in analysis.split("\n"):
            if line.strip().startswith(prefix):
                text = line.split(":", 1)[1].strip()
                if text:
                    brain["lessons"].append({
                        "id":       len(brain["lessons"]) + 1,
                        "text":     f"[{prefix[:-1]}] {text}",
                        "category": "meta_pattern",
                        "date":     datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d %H:%M"),
                    })
                    lessons_added += 1

    # שמור גם trade_notes מלאות
    brain["trade_notes"] = brain.get("trade_notes", [])
    brain["trade_notes"].append({
        "date":    datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d %H:%M"),
        "summary": "היסטוריה מלאה נטענה — EVAL1 + LUCID2 + CLAUDE1 | 20+ עסקאות",
        "rules":   "28 כללי ברזל נלמדו",
    })

    brain["updated_at"] = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d %H:%M")
    BRAIN_FILE.write_bytes(json.dumps(brain, ensure_ascii=False, indent=2).encode("utf-8"))

    print("=" * 60)
    print(f"[OK] {lessons_added} לקחים נשמרו לזיכרון של ג'ימי")
    print(f"[book] סה\"כ בזיכרון: {len(brain['lessons'])} לקחים")
    print()

    # ── שלב 3: שמור גם ל-trade_journal.json ──
    journal_file = DATA_DIR / "trade_journal.json"
    try:
        journal = json.loads(journal_file.read_text(encoding="utf-8"))
    except Exception:
        journal = []

    # בדוק אם ההיסטוריה כבר נטענה
    existing_ids = {t.get("id") for t in journal}

    historical_trades = [
        {"id":"EVAL1_T1","account":"EVAL1","date":"2026-05-21","action":"SHORT","entry_price":29399.5,"exit_price":29260.5,"pnl_pts":139,"sl":29427,"tp":29260,"rr":3.5,"result":"WIN","lesson":"ICT sweep below 5-bar low + HTF alignment = perfect setup"},
        {"id":"EVAL1_T2","account":"EVAL1","date":"2026-05-21","action":"SHORT","entry_price":29257,"exit_price":29285,"pnl_pts":-28,"result":"LOSS","lesson":"נכנסתי ישר אחרי WIN ללא סטאפ חדש"},
        {"id":"EVAL1_T3","account":"EVAL1","date":"2026-05-21","action":"LONG","entry_price":29270,"exit_price":29275,"pnl_pts":5,"result":"BE","lesson":"כניסה ללא candle close"},
        {"id":"EVAL1_T4","account":"EVAL1","date":"2026-05-22","action":"SHORT","entry_price":29665,"exit_price":29712.5,"pnl_pts":-47.5,"result":"LOSS","lesson":"SL בתוך liquidity zone"},
        {"id":"EVAL1_T5","account":"EVAL1","date":"2026-05-22","action":"LONG","entry_price":29577.5,"exit_price":29537.5,"pnl_pts":-40,"result":"LOSS","lesson":"כניסה אחרי 2 הפסדים — over-trading"},
        {"id":"EVAL1_T6","account":"EVAL1","date":"2026-05-22","action":"SHORT","entry_price":29628,"exit_price":29670,"pnl_pts":-42,"result":"LOSS","lesson":"כניסה 3 ביום ללא candle close"},
        {"id":"LUCID2_T1","account":"LUCID2","date":"2026-05-25","action":"LONG","entry_price":29948,"exit_price":29932.5,"pnl_pts":-15.5,"result":"LOSS","lesson":"ללא HTF confirmation — TP נפגע אחרי SL"},
        {"id":"CLAUDE1_T3","account":"CLAUDE1","date":"2026-05-28","action":"LONG","entry_price":29981.25,"exit_price":29963,"pnl_pts":-18,"result":"LOSS","lesson":"ClaudeStrategy כובה ידנית — missed 265 pts"},
        {"id":"CLAUDE1_T4","account":"CLAUDE1","date":"2026-05-28","action":"LONG","entry_price":30150,"exit_price":30117,"pnl_pts":-33,"result":"LOSS","lesson":"Capitulation Rule — יציאה על CDH rejection"},
        {"id":"CLAUDE1_T5","account":"CLAUDE1","date":"2026-05-28","action":"SHORT","entry_price":30128.5,"exit_price":30150,"pnl_pts":-21.5,"result":"LOSS","lesson":"SELL כשFLAT = stale position.json — SHORT שגגה"},
        {"id":"CLAUDE1_T5B","account":"CLAUDE1","date":"2026-06-01","action":"LONG","entry_price":30337,"exit_price":30379,"pnl_pts":43,"result":"WIN","lesson":"AMD pattern + Capitulation + trigger מחיר ברור = WIN"},
        {"id":"CLAUDE1_T1_0602","account":"CLAUDE1","date":"2026-06-02","action":"LONG","entry_price":30620,"exit_price":30609,"pnl_pts":-11,"result":"LOSS","lesson":"CDH retest ללא בר סגור מעל CDH"},
        {"id":"CLAUDE1_T2_0602","account":"CLAUDE1","date":"2026-06-02","action":"LONG","entry_price":30615,"exit_price":30586,"pnl_pts":-29,"result":"LOSS","lesson":"Capitulation false — delta +590 בדקה 1, סגר -4828"},
        {"id":"CLAUDE1_T3_0602","account":"CLAUDE1","date":"2026-06-02","action":"SHORT","entry_price":30698,"exit_price":30703,"pnl_pts":-21,"result":"LOSS","lesson":"BSL sweep vs breakout — לא ידעתי להבדיל"},
        {"id":"CLAUDE1_T15","account":"CLAUDE1","date":"2026-06-10","action":"SHORT","entry_price":29028.75,"exit_price":29256,"pnl_pts":-146,"result":"LOSS","lesson":"SL=0 לא נשמר + position_monitor לא הופעל — Rule 16+23"},
    ]

    added = 0
    for t in historical_trades:
        t["opened_at"] = t["date"] + " 17:00:00"
        if t["id"] not in existing_ids:
            journal.append(t)
            added += 1

    journal_file.write_bytes(json.dumps(journal, ensure_ascii=False, indent=2).encode("utf-8"))
    print(f"[log] {added} עסקאות נשמרו ב-trade_journal.json")
    print()
    print("[*] ג'ימי למד את כל ההיסטוריה שלו!")
    print("   עכשיו הוא יודע מה עובד ומה לא — ב-100% מהמקרים.")


if __name__ == "__main__":
    teach_jimmy()
