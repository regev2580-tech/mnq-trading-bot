"""
jimmy_research.py — ג'ימי לומד, חוקר, ומתכנן כמו פרופ-טריידר
═══════════════════════════════════════════════════════════════════
לוח כלכלי + תכנית סשן + סיכום + מחקר ברשת
לוח יומי:
  09:00 — מחקר בוקר + לוח כלכלי
  15:30 — בדיקה לפני KZ — אזהרה אם HIGH IMPACT
  16:00 — תכנית סשן מלאה עם triggers
  18:30 — סיכום + לקחים
"""

import json
import os
import time
import anthropic
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

HAS_DDG = False
try:
    from ddgs import DDGS
    HAS_DDG = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        HAS_DDG = True
    except ImportError:
        pass

ISRAEL_TZ         = timezone(timedelta(hours=3))
DATA_DIR          = Path(r"C:\Users\regev\New folder\ninjatrader-mcp\data")
TODAY_EVENTS_FILE = DATA_DIR / "today_events.json"
DAILY_PLAN_FILE   = DATA_DIR / "daily_plan.json"

from jimmy_web import add_lesson, load_brain

RESEARCH_TOPICS = [
    "ICT 2022 NQ futures trading strategy order flow",
    "MNQ NQ kill zone AM session trading setup",
    "Valtos order flow trading futures delta CVD",
    "ICT inner circle trader concepts 2026",
    "NQ futures market structure liquidity sweep",
    "futures trading capitulation order flow absorption",
    "ICT AMD accumulation manipulation distribution",
    "order flow trading bid ask imbalance futures",
    "ICT power of 3 NQ futures AM kill zone",
    "NQ futures CVD divergence signal entry",
]

# ── רשימת נושאים מורחבת ללמידה עצמאית ──
LEARNING_TOPICS: dict[str, list[str]] = {
    "ICT_core": [
        "ICT order block trading NQ futures entry signal",
        "ICT fair value gap FVG fill strategy NQ",
        "ICT breaker block vs order block difference",
        "ICT optimal trade entry OTE 62% retracement NQ",
        "ICT silver bullet strategy 10am 2pm NQ futures",
        "ICT CISD change state delivery NQ",
        "ICT SMT divergence NQ ES correlation signal",
        "ICT PDA arrays premium discount price delivery",
        "ICT displacement candle NQ momentum entry",
        "ICT balanced price range BPR void fill",
        "ICT judas swing manipulation phase NQ",
        "ICT London open killzone NQ strategy",
        "ICT institutional order flow entry drill explained",
        "ICT consequent encroachment CE level",
        "ICT propulsion block NQ futures",
    ],
    "orderflow_advanced": [
        "CVD cumulative volume delta divergence trading signal",
        "delta divergence futures reversal entry NQ",
        "stacked bid ask imbalances footprint chart NQ",
        "absorption volume futures reversal signal",
        "footprint chart trading NQ 5 minute",
        "volume profile POC value area NQ day trading",
        "market profile TPO NQ futures strategy",
        "trapped traders order flow detection futures",
        "iceberg orders futures hidden liquidity",
        "aggressive buying selling delta imbalance NQ",
        "CVD momentum mode trending market NQ futures",
        "bid ask delta exhaustion signal futures",
        "volume weighted average price VWAP NQ strategy",
        "cumulative delta reset session NQ futures",
    ],
    "market_structure": [
        "market structure break MSB NQ futures signal",
        "higher timeframe alignment HTF LTF confluence",
        "change of character CHOCH NQ market structure",
        "internal liquidity external liquidity sweep NQ",
        "inducement IDM before displacement NQ",
        "equal highs lows liquidity pool NQ futures",
        "price delivery algorithm PDA NQ explanation",
        "swing failure pattern SFP NQ futures",
        "range expansion compression NQ AM session",
        "gap fill strategy NQ futures morning",
    ],
    "risk_management": [
        "position sizing futures prop firm rules",
        "risk reward 2R 3R optimization futures trading",
        "breakeven management futures stop loss",
        "partial profit taking scale out futures NQ",
        "max loss daily drawdown prop firm futures",
        "correlation risk NQ ES YM futures hedge",
        "trailing stop loss futures NQ strategy",
        "multiple timeframe SL placement futures",
    ],
    "session_analysis": [
        "NY AM kill zone 930am NQ futures best setups",
        "pre-market analysis NQ futures gap open strategy",
        "NQ futures first 30 minutes volatility",
        "NY PM session NQ futures afternoon setup",
        "NQ futures daily range typical distribution",
        "NQ futures monday tuesday patterns weekly",
        "news release strategy NQ futures CPI FOMC",
        "NQ futures overnight session analysis",
    ],
    "psychology_discipline": [
        "trading discipline waiting for setup futures",
        "fear missing out FOMO futures trading mistake",
        "overtrading prevention prop firm futures",
        "patience kill zone setup futures psychology",
        "revenge trading prevention futures losses",
        "trading journal review improve futures",
        "rule based trading system futures discipline",
        "emotional control futures day trading",
    ],
    "advanced_concepts": [
        "intermarket analysis NQ VIX DXY correlation",
        "NQ futures seasonality monthly weekly patterns",
        "dark pool orders futures institutional activity",
        "options gamma exposure NQ futures impact",
        "futures contract rollover NQ September impact",
        "algorithmic trading patterns NQ AM session",
        "macro economic impact NQ futures CPI NFP",
        "NQ futures liquidity landscape morning",
    ],
}

# ──────────────────────────────────────────────
# חיפוש בסיסי
# ──────────────────────────────────────────────

def _web_search(query: str, max_results: int = 5) -> list[dict]:
    if not HAS_DDG:
        return []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results
    except Exception as e:
        print(f"[Research] Search error: {e}")
        return []


def _extract_insight(query: str, results: list[dict]) -> str | None:
    if not results:
        return None
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    snippets = "\n\n".join([
        f"Title: {r.get('title','')}\n{r.get('body','')[:400]}"
        for r in results[:4]
    ])
    prompt = f"""אתה ג'ימי — סוחר MNQ עם ICT 2022 + Valtos Order Flow.
חיפשתי: "{query}"

תוצאות:
{snippets}

חלץ תובנה אחת מעשית שתעזור לי לסחור טוב יותר ב-Kill Zone של NQ/MNQ.
אם אין שום דבר שימושי — ענה NULL.
אחרת: INSIGHT: [תובנה קצרה ומעשית — משפט אחד או שניים]
"""
    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        if "NULL" in text or not text:
            return None
        for line in text.split("\n"):
            if line.startswith("INSIGHT:"):
                return line.replace("INSIGHT:", "").strip()
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────
# לוח כלכלי — הלב של המערכת
# ──────────────────────────────────────────────

def check_economic_calendar() -> dict:
    """
    בודק אירועים כלכליים HIGH IMPACT להיום.
    שומר ל-today_events.json.
    מחזיר dict מובנה עם has_high_impact, during_kz, decision.
    """
    now       = datetime.now(ISRAEL_TZ)
    today     = now.strftime("%Y-%m-%d")
    day_str   = now.strftime("%A %B %d %Y")

    print(f"[{now.strftime('%H:%M')}] בודק לוח כלכלי — {today}")

    results = []
    for q in [
        f"economic calendar {day_str} high impact USD",
        f"US economic releases today {today} FOMC CPI NFP fed meeting",
        f"forex economic calendar today {today} USD high impact events",
    ]:
        results.extend(_web_search(q, max_results=4))

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    snippets = "\n\n".join([
        f"[{r.get('title','')}]\n{r.get('body','')[:400]}"
        for r in results[:6]
    ]) or "לא נמצאו תוצאות — ייתכן שהאינטרנט לא זמין"

    # is_nfp: ראשון שישי בחודש
    is_nfp = now.weekday() == 4 and now.day <= 7

    prompt = f"""אתה ג'ימי — סוחר MNQ שמנהל סיכון כמו פרופ.
היום: {day_str}
NFP Friday: {'כן!' if is_nfp else 'לא'}

נתונים שמצאתי על הלוח הכלכלי:
{snippets}

זהה כל אירוע HIGH IMPACT שמשפיע על NQ/USD:
FOMC, Federal Reserve Rate Decision, CPI, NFP, GDP, PPI,
Retail Sales, Initial Jobless Claims, PCE, Powell Speech

עבור כל אירוע שמצאת:
EVENT: [שם האירוע] | TIME_UTC: [HH:MM] | TIME_ISRAEL: [HH:MM] | IMPACT: HIGH/MEDIUM | DURING_KZ: YES/NO

Kill Zone = 13:30–15:00 UTC = 16:30–18:00 ישראל

אם אין אירועים HIGH IMPACT היום: NO_HIGH_IMPACT_TODAY

לפי מה שמצאת, ענה:
TRADING_DECISION: NORMAL / REDUCE_SIZE / WAIT_AFTER_EVENT / SKIP_DAY
REASON: [הסבר קצר]
SUMMARY: [משפט אחד — מה עלי לדעת לפני KZ]
"""

    result = {
        "date":             today,
        "checked_at":       now.strftime("%H:%M"),
        "events":           [],
        "has_high_impact":  False,
        "during_kz":        False,
        "is_nfp":           is_nfp,
        "trading_decision": "NORMAL",
        "reason":           "",
        "summary":          "",
        "raw":              "",
    }

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        result["raw"] = text

        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("EVENT:"):
                result["events"].append(line)
                if "HIGH" in line:
                    result["has_high_impact"] = True
                if "DURING_KZ: YES" in line or "YES" in line.split("|")[-1]:
                    result["during_kz"] = True
            elif line.startswith("TRADING_DECISION:"):
                result["trading_decision"] = line.split(":", 1)[1].strip()
            elif line.startswith("REASON:"):
                result["reason"] = line.split(":", 1)[1].strip()
            elif line.startswith("SUMMARY:"):
                result["summary"] = line.split(":", 1)[1].strip()

        if is_nfp:
            result["has_high_impact"] = True
            result["trading_decision"] = "SKIP_DAY"
            result["summary"] = "NFP Friday — Rule 24: אסור לסחור בלי אישור מפורש"

        if not result["summary"]:
            result["summary"] = "לא נמצאו אירועים HIGH IMPACT — מסחר רגיל" if not result["has_high_impact"] else "יש אירועים HIGH IMPACT — בדוק!"

    except Exception as e:
        result["summary"] = f"שגיאה בבדיקת לוח: {e}"

    # שמור לקובץ
    try:
        TODAY_EVENTS_FILE.write_bytes(
            json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
        )
    except Exception:
        pass

    # שמור לזיכרון אם HIGH IMPACT
    if result["has_high_impact"]:
        add_lesson(
            f"[לוח {today}] {result['summary']}",
            "economic_calendar"
        )

    print(f"[{now.strftime('%H:%M')}] לוח: {result['summary']}")
    return result


def get_today_events() -> dict:
    """קרא today_events.json — אם לא קיים או ישן, בדוק עכשיו"""
    try:
        data  = json.loads(TODAY_EVENTS_FILE.read_text(encoding="utf-8"))
        today = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")
        if data.get("date") == today:
            return data
    except Exception:
        pass
    return check_economic_calendar()


# ──────────────────────────────────────────────
# תכנית סשן — נכתבת ב-16:00
# ──────────────────────────────────────────────

def presession_prep() -> str:
    """
    תכנית מסחר מלאה לפני KZ — נקראת ב-16:00.
    כולל: bias, רמות, triggers, לוח כלכלי, לקחים מהזיכרון.
    """
    now_str = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d %H:%M")
    print(f"[{now_str[11:]}] מכין תכנית סשן לפני KZ...")

    events    = get_today_events()
    brain     = load_brain()
    of_data   = {}
    bias_data = {}
    state_data = {}

    try:
        of_data = json.loads((DATA_DIR / "orderflow.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    try:
        bias_data = json.loads((DATA_DIR / "session_bias.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    try:
        state_data = json.loads((DATA_DIR / "jimmy_state.json").read_text(encoding="utf-8"))
    except Exception:
        pass

    # חשב CVD נוכחי
    price_now = of_data.get("price", "לא זמין")
    cvd_now   = "לא זמין"
    bars      = of_data.get("bars", [])
    if bars:
        cvd_now = round(sum(b.get("delta", 0) for b in bars), 0)

    # לקחים אחרונים
    lessons_recent = brain.get("lessons", [])[-8:]
    lessons_text   = "\n".join([f"• [{l['date']}] {l['text']}" for l in lessons_recent]) or "אין עדיין"

    # היסטוריית עסקאות היום
    trades_today = state_data.get("trades_today", 0)
    signals_today = state_data.get("signals", [])

    prompt = f"""אתה ג'ימי — סוחר MNQ מקצועי שמכין את עצמו לפני Kill Zone.
אתה לא מחכה שיגידו לך מה לעשות — אתה בונה תכנית ומבצע אותה.

=== PRE-SESSION PREP | {now_str} ===

נתוני שוק נוכחיים (NT8):
• מחיר: {price_now}
• CVD (10 bars): {cvd_now}
• HTF Bias: {bias_data.get('htf_bias', 'לא ידוע')}
• CDH: {of_data.get('cdh', '?')} | CDL: {of_data.get('cdl', '?')}
• PDH: {of_data.get('pdh', '?')} | PDL: {of_data.get('pdl', '?')}
• Delta נוכחי: {of_data.get('current_delta', 0):+d}

לוח כלכלי היום:
• {events.get('summary', 'לא נבדק')}
• NFP: {'כן!' if events.get('is_nfp') else 'לא'}
• HIGH IMPACT: {'כן — ' + str(events.get('events', [])) if events.get('has_high_impact') else 'לא'}
• During KZ: {'כן — חשוב!' if events.get('during_kz') else 'לא'}
• Decision: {events.get('trading_decision', 'NORMAL')}

עסקאות היום עד כה:
• {trades_today} / 2 | {json.dumps(signals_today, ensure_ascii=False)}

לקחים אחרונים מהזיכרון:
{lessons_text}

כתוב תכנית סשן מלאה כמו פרופ-טריידר:

BIAS: [BULLISH/BEARISH/NEUTRAL] — [הסבר קצר מדוע]

KEY_LEVELS:
• מעל: [רמה] ([מה היא])
• מתחת: [רמה] ([מה היא])
• טריגר: [רמה קריטית שמשחקת תפקיד היום]

LONG_TRIGGER: [אם _____ קורה ב-16:50–17:20 → LONG @ _____ | SL _____ | TP _____ | R/R _____]
SHORT_TRIGGER: [אם _____ קורה ב-16:50–17:20 → SHORT @ _____ | SL _____ | TP _____ | R/R _____]

RISK_LEVEL: [NORMAL / REDUCED / SKIP] — [סיבה]

WHAT_TO_AVOID:
• [דבר ספציפי שעלי להימנע ממנו היום]

MY_EDGE_TODAY: [מה הסיכוי שלי להיות רווחי היום ולמה]

תן תכנית ספציפית, מספרית, מוכנה לביצוע. לא כללית.
"""

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    try:
        response = client.messages.create(
            model      = "claude-opus-4-8",   # opus — תכנון חשוב
            max_tokens = 900,
            thinking   = {"type": "adaptive"},
            messages   = [{"role": "user", "content": prompt}]
        )
        plan = next(
            (b.text for b in response.content if b.type == "text"),
            "שגיאה: אין תשובה"
        )

        plan_data = {
            "date":   now_str[:10],
            "time":   now_str[11:],
            "plan":   plan,
            "events": events.get("events", []),
            "bias":   bias_data.get("htf_bias", "UNKNOWN"),
        }
        DAILY_PLAN_FILE.write_bytes(
            json.dumps(plan_data, ensure_ascii=False, indent=2).encode("utf-8")
        )

        print(f"[{now_str[11:]}] תכנית סשן נכתבה ✅")
        return plan

    except Exception as e:
        error_plan = f"שגיאה בהכנת תכנית: {e}"
        print(error_plan)
        return error_plan


def get_daily_plan() -> dict:
    """קרא daily_plan.json של היום"""
    try:
        data  = json.loads(DAILY_PLAN_FILE.read_text(encoding="utf-8"))
        today = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")
        if data.get("date") == today:
            return data
    except Exception:
        pass
    return {}


# ──────────────────────────────────────────────
# סיכום סשן — 18:30 אחרי KZ
# ──────────────────────────────────────────────

def postsession_review() -> str:
    """
    סיכום KZ — נקרא ב-18:30.
    מנתח: מה בוצע, האם התכנית הושמרה, מה לשפר מחר.
    """
    now_str = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d %H:%M")
    print(f"[{now_str[11:]}] מסכם סשן...")

    state_data   = {}
    today_trades = []
    plan_data    = get_daily_plan()
    events       = get_today_events()

    try:
        state_data = json.loads((DATA_DIR / "jimmy_state.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    try:
        journal = json.loads((DATA_DIR / "trade_journal.json").read_text(encoding="utf-8"))
        today   = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")
        today_trades = [t for t in journal if t.get("opened_at", "").startswith(today)]
    except Exception:
        pass

    trades_count  = state_data.get("trades_today", len(today_trades))
    signals_today = state_data.get("signals", [])

    # חשב P&L
    total_pnl = sum(t.get("pnl_pts", 0) for t in today_trades)
    wins  = sum(1 for t in today_trades if t.get("pnl_pts", 0) > 0)
    losses = sum(1 for t in today_trades if t.get("pnl_pts", 0) < 0)

    prompt = f"""אתה ג'ימי — סוחר MNQ. KZ הסתיימה. זה הרגע שאתה מסתכל אחורה ולומד.
עכשיו: {now_str}

=== POST-SESSION REVIEW ===

תכנית שכתבתי ב-16:00:
{plan_data.get('plan', 'לא הוכנה תכנית')[:600]}

מה ביצעתי בפועל:
• עסקאות: {trades_count}
• P&L: {total_pnl:+.1f} pts
• ניצחונות: {wins} | הפסדים: {losses}
• Signals: {json.dumps(signals_today, ensure_ascii=False)}

פרטי עסקאות:
{json.dumps(today_trades, ensure_ascii=False)[:600] if today_trades else 'אין עסקאות'}

לוח כלכלי של היום:
{events.get('summary', 'לא רלוונטי')}

ענה כמו סוחר שמדבר לעצמו אחרי הסשן:

SESSION_RESULT: WIN/LOSS/FLAT/NO_TRADES
P&L: {total_pnl:+.1f} pts

FOLLOWED_PLAN: YES/NO/PARTIAL
WHY: [הסבר קצר]

WHAT_WORKED: [מה עבד היום]
WHAT_FAILED: [מה לא עבד]
BIGGEST_MISTAKE: [הטעות הכי גדולה אם יש]
MISSED_OPPORTUNITY: [הזדמנות שפספסתי אם יש]

TOMORROW: [דבר אחד ספציפי שאשנה מחר]
LESSON: [לקח אחד לזיכרון]

קצר, ישיר, בלי לחמם את הכיסא.
"""

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        review = response.content[0].text.strip()

        # שמור לקח לזיכרון
        for line in review.split("\n"):
            if line.startswith("LESSON:"):
                lesson = line.replace("LESSON:", "").strip()
                if lesson:
                    add_lesson(f"[סיכום {now_str[:10]}] {lesson}", "session_review")

        print(f"[{now_str[11:]}] סיכום סשן הושלם ✅ | P&L: {total_pnl:+.1f} pts")
        return review

    except Exception as e:
        return f"שגיאה בסיכום: {e}"


# ──────────────────────────────────────────────
# מחקר נושאים
# ──────────────────────────────────────────────

def research_topic(topic: str) -> str:
    """חפש נושא ספציפי — זמין מהצ'אט"""
    print(f"[{datetime.now(ISRAEL_TZ).strftime('%H:%M')}] חוקר: {topic}")
    results = _web_search(topic, max_results=6)
    if not results:
        return f"לא מצאתי תוצאות עבור: {topic}"
    insight = _extract_insight(topic, results)
    if insight:
        add_lesson(f"[מחקר רשת] {insight}", category="web_research")
        return f"תובנה חדשה: {insight}"
    return f"חיפשתי '{topic}' — לא מצאתי תובנה ממשית"


def research_concept(concept: str) -> str:
    """מחקר מעמיק על קונספט ICT/Trading ספציפי — Opus"""
    queries = [
        f"ICT {concept} futures trading explained",
        f"{concept} NQ MNQ futures strategy",
        f"Valtos order flow {concept}",
    ]
    client       = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    all_snippets = []
    for q in queries:
        for r in _web_search(q, max_results=3):
            all_snippets.append(f"[{r.get('title','')}]\n{r.get('body','')[:500]}")
    if not all_snippets:
        return f"לא מצאתי מידע על: {concept}"

    prompt = f"""אתה ג'ימי, סוחר MNQ ICT 2022. רוצה להעמיק ב: "{concept}"

מה שמצאתי:
{chr(10).join(all_snippets[:6])}

סכם:
1. הגדרה מדויקת של {concept}
2. איך לזהות בגרף NQ 5M
3. Entry trigger מדויק
4. SL מתאים
5. לקח מרכזי אחד
"""
    try:
        response = client.messages.create(
            model      = "claude-opus-4-8",
            max_tokens = 800,
            messages   = [{"role": "user", "content": prompt}]
        )
        result = response.content[0].text.strip()
        add_lesson(f"[מחקר: {concept}] {result[:200]}...", category="concept_research")
        return result
    except Exception as e:
        return f"שגיאה: {e}"


# ──────────────────────────────────────────────
# מחקר בוקר — 9:00 כל יום
# ──────────────────────────────────────────────

def morning_research():
    """מחקר בוקר אוטומטי — לוח כלכלי + NQ context + ICT topic"""
    today   = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")
    now_str = datetime.now(ISRAEL_TZ).strftime("%H:%M")
    print(f"[{now_str}] מחקר בוקר — {today}")

    new_insights = []

    # 1. לוח כלכלי — ראשון ועיקרי
    events = check_economic_calendar()
    if events.get("has_high_impact"):
        msg = f"HIGH IMPACT היום: {events['summary']}"
    else:
        msg = events.get("summary", "אין אירועים HIGH IMPACT")
    new_insights.append(msg)
    print(f"[{now_str}] לוח: {msg}")

    # 2. ניתוח NQ
    nq_results = _web_search(f"NQ NQ100 futures market analysis {today}", max_results=5)
    nq_insight  = _extract_insight("NQ futures today analysis", nq_results)
    if nq_insight:
        new_insights.append(nq_insight)
        add_lesson(f"[בוקר {today}] NQ: {nq_insight}", "morning_research")

    # 3. חדשות USD/macro
    macro_results = _web_search(f"US dollar DXY macro economic news {today}", max_results=4)
    macro_insight = _extract_insight("USD macro news today affecting NQ", macro_results)
    if macro_insight:
        new_insights.append(macro_insight)
        add_lesson(f"[בוקר {today}] Macro: {macro_insight}", "morning_research")

    # 4. תובנת ICT אקראית
    topic      = random.choice(RESEARCH_TOPICS)
    ict_results = _web_search(topic, max_results=5)
    ict_insight = _extract_insight(topic, ict_results)
    if ict_insight:
        new_insights.append(ict_insight)
        add_lesson(f"[ICT] {ict_insight}", "ict_research")

    summary = f"בוקר {today}: {len(new_insights)} תובנות\n" + "\n".join(f"• {i}" for i in new_insights)
    print(summary)
    return summary


# ──────────────────────────────────────────────
# למידה עצמאית — ג'ימי לומד בזמן הפנוי
# ──────────────────────────────────────────────

LEARNED_FILE = DATA_DIR / "learned_topics.json"


def _get_learned_topics() -> set:
    """קרא רשימת נושאים שכבר נלמדו"""
    try:
        data = json.loads(LEARNED_FILE.read_text(encoding="utf-8"))
        return set(data.get("topics", []))
    except Exception:
        return set()


def _mark_learned(topic: str):
    """סמן נושא כנלמד"""
    try:
        data = json.loads(LEARNED_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {"topics": [], "count": 0}
    if topic not in data["topics"]:
        data["topics"].append(topic)
        data["count"] = len(data["topics"])
        data["last_learned"] = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d %H:%M")
        LEARNED_FILE.write_bytes(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))


def _pick_learning_topic(weakness_topics: list[str] | None = None) -> tuple[str, str]:
    """
    בחר נושא ללמידה בצורה חכמה:
    1. קודם כל — חולשות שזוהו מהעסקאות
    2. אחר כך — נושאים שעוד לא נלמדו
    3. לבסוף — חזרה על נושאים ישנים
    מחזיר (category, topic)
    """
    learned = _get_learned_topics()

    # קודם חולשות
    if weakness_topics:
        for t in weakness_topics:
            if t not in learned:
                return ("weakness", t)

    # אחר כך נושאים חדשים לפי קטגוריה
    all_categories = list(LEARNING_TOPICS.keys())
    random.shuffle(all_categories)

    for cat in all_categories:
        topics = LEARNING_TOPICS[cat]
        new_topics = [t for t in topics if t not in learned]
        if new_topics:
            return (cat, random.choice(new_topics))

    # כולם נלמדו — בחר אקראי לחזרה
    cat   = random.choice(all_categories)
    topic = random.choice(LEARNING_TOPICS[cat])
    return (cat, topic)


def identify_weaknesses() -> list[str]:
    """
    מנתח את היסטוריית העסקאות ומוצא חולשות.
    מחזיר רשימת queries ספציפיים לחקור.
    """
    try:
        journal = json.loads((DATA_DIR / "trade_journal.json").read_text(encoding="utf-8"))
    except Exception:
        return []

    if not journal:
        return []

    losses      = [t for t in journal if t.get("pnl_pts", 0) < 0]
    total       = len(journal)
    loss_count  = len(losses)

    weakness_topics = []

    # חולשה: כניסות מוקדמות (לפני 16:50)
    early_losses = [t for t in losses if t.get("opened_at", "")[-8:-3] < "16:50"]
    if len(early_losses) > 1:
        weakness_topics.append("ICT kill zone timing entry discipline 9:30am rule")

    # חולשה: CVD שלילי בכניסה
    cvd_losses = [t for t in losses if t.get("entry_cvd", 0) < -500]
    if len(cvd_losses) > 1:
        weakness_topics.append("CVD negative momentum futures trading against trend mistake")

    # חולשה: SL קצר מדי
    sl_losses = [t for t in losses if abs(t.get("entry_price", 0) - t.get("sl", 0)) < 15]
    if len(sl_losses) > 1:
        weakness_topics.append("stop loss placement futures NQ sweep distance minimum")

    # חולשה: R/R נמוך
    rr_losses = [t for t in losses if t.get("rr", 0) < 2.0]
    if len(rr_losses) > 1:
        weakness_topics.append("risk reward ratio minimum 2R futures trade selection")

    # חולשה: יציאה מוקדמת (counterfactuals)
    early_exits = [t for t in journal if t.get("counterfactuals", {}).get("tp_was_hit_after_close")]
    if len(early_exits) > 1:
        weakness_topics.append("holding winners futures trading target exit discipline")

    # חולשה: loss rate גבוה
    if total > 5 and loss_count / total > 0.6:
        weakness_topics.append("trade selection filter high probability ICT setups only")

    return weakness_topics


def free_time_learning() -> str:
    """
    סשן למידה עצמאי — ג'ימי לומד נושא אחד לעומק.
    כולל: חיפוש + קריאה + ניתוח + שמירה לזיכרון.
    """
    now_str = datetime.now(ISRAEL_TZ).strftime("%H:%M")

    # זהה חולשות ובחר נושא
    weaknesses  = identify_weaknesses()
    cat, topic  = _pick_learning_topic(weaknesses)

    print(f"[{now_str}] למידה עצמאית | קטגוריה: {cat} | נושא: {topic[:50]}")

    # חפש ברשת
    results = _web_search(topic, max_results=6)
    if not results:
        print(f"[{now_str}] אין תוצאות לנושא זה — מדלג")
        return f"לא נמצאו תוצאות: {topic}"

    # בנה snippets
    snippets = "\n\n".join([
        f"[{r.get('title','')}]\n{r.get('body','')[:600]}"
        for r in results[:5]
    ])

    # שלח לקלוד לניתוח מעמיק
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    brain_context = ""
    try:
        brain = load_brain()
        recent = brain.get("lessons", [])[-5:]
        brain_context = "\n".join([f"• {l['text']}" for l in recent])
    except Exception:
        pass

    prompt = f"""אתה ג'ימי — סוחר MNQ שמשתפר כל יום. עכשיו {now_str}, אתה לומד בזמן החופשי שלך.

נושא: "{topic}"
קטגוריה: {cat}

מה שמצאתי ברשת:
{snippets}

מה שכבר יודע (לקחים אחרונים):
{brain_context or 'עדיין לומד'}

למד את הנושא לעומק וענה:

WHAT_I_LEARNED: [הסבר קצר מה הנושא — 2-3 משפטים]
HOW_TO_APPLY: [איך אני מיישם את זה ב-KZ של NQ — משפט אחד קונקרטי עם מספרים]
RULE_CANDIDATE: [האם זה מוסיף/מחדד כלל קיים? כן/לא — אם כן, מה הכלל המדויק]
CONFIDENCE: [1-5 — כמה אני בטוח בתובנה הזו]
NEXT_TO_LEARN: [נושא קשור שכדאי ללמוד אחר כך]

ענה בפורמט הזה בדיוק. קצר, מדויק, מעשי.
"""

    try:
        response = client.messages.create(
            model      = "claude-haiku-4-5",   # מהיר וזול לסשני למידה
            max_tokens = 500,
            messages   = [{"role": "user", "content": prompt}]
        )
        analysis = response.content[0].text.strip()

        # חלץ ושמור לזיכרון
        learned_text = ""
        next_topic   = ""

        for line in analysis.split("\n"):
            if line.startswith("WHAT_I_LEARNED:"):
                learned_text = line.split(":", 1)[1].strip()
            elif line.startswith("HOW_TO_APPLY:"):
                apply_text = line.split(":", 1)[1].strip()
                if learned_text:
                    add_lesson(
                        f"[{cat}] {topic[:40]}: {apply_text}",
                        category=f"self_study_{cat}"
                    )
            elif line.startswith("RULE_CANDIDATE:") and "כן" in line:
                rule_text = line.split(":", 1)[1].strip()
                add_lesson(f"[כלל חדש מלמידה] {rule_text}", category="new_rule")
            elif line.startswith("NEXT_TO_LEARN:"):
                next_topic = line.split(":", 1)[1].strip()

        # סמן כנלמד
        _mark_learned(topic)

        print(f"[{now_str}] למידה הושלמה ✅ | {topic[:40]}")
        if next_topic:
            print(f"[{now_str}] הבא: {next_topic}")

        return f"למדתי: {learned_text[:100] if learned_text else topic}"

    except Exception as e:
        print(f"[{now_str}] שגיאת למידה: {e}")
        return f"שגיאה: {e}"


def get_learning_stats() -> dict:
    """סטטיסטיקות למידה — כמה נושאים נלמדו"""
    try:
        data = json.loads(LEARNED_FILE.read_text(encoding="utf-8"))
        total_available = sum(len(v) for v in LEARNING_TOPICS.values())
        return {
            "learned_count":    data.get("count", 0),
            "total_available":  total_available,
            "last_learned":     data.get("last_learned", "אף פעם"),
            "percentage":       round(data.get("count", 0) / total_available * 100),
        }
    except Exception:
        return {"learned_count": 0, "total_available": sum(len(v) for v in LEARNING_TOPICS.values()), "percentage": 0}


# ──────────────────────────────────────────────
# Scheduler — לוח יומי מלא
# ──────────────────────────────────────────────

_done_today: dict = {}


def _once_today(key: str) -> bool:
    """האם כבר ביצענו פעולה זו היום?"""
    today = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")
    if _done_today.get(key) == today:
        return True
    _done_today[key] = today
    return False


def _safe_run(name: str, fn):
    """הרץ פונקציה עם exception handling"""
    try:
        fn()
    except Exception as e:
        print(f"[Scheduler] {name} שגיאה: {e}")


def research_scheduler_loop():
    """
    לולאה 24/7 — הלוח היומי המלא של ג'ימי:

    09:00 → מחקר בוקר + לוח כלכלי
    10:00 → למידה עצמאית #1 (ICT / OrderFlow)
    12:00 → למידה עצמאית #2 (Market Structure / Risk)
    14:00 → למידה עצמאית #3 (Pre-KZ — strategy review)
    15:30 → אזהרה אם HIGH IMPACT DURING KZ
    16:00 → תכנית סשן מלאה עם triggers
    16:30 → KZ — מסחר אוטומטי (jimmy.py)
    18:30 → סיכום סשן + לקחים
    19:30 → למידה עצמאית #4 (ניתוח מה שקרה בשוק)
    21:00 → למידה עצמאית #5 (Psychology / Advanced)
    """
    while True:
        now  = datetime.now(ISRAEL_TZ)
        h, m = now.hour, now.minute

        # 09:00 — מחקר בוקר + לוח כלכלי
        if h == 9 and m < 5 and not _once_today("morning"):
            _safe_run("morning_research", morning_research)

        # 10:00 — למידה #1
        elif h == 10 and m < 5 and not _once_today("learn_1"):
            def learn1():
                result = free_time_learning()
                stats  = get_learning_stats()
                print(f"[10:00] למידה #1: {result} | סה\"כ נלמד: {stats['learned_count']}/{stats['total_available']}")
            _safe_run("free_learning_1", learn1)

        # 12:00 — למידה #2
        elif h == 12 and m < 5 and not _once_today("learn_2"):
            def learn2():
                result = free_time_learning()
                print(f"[12:00] למידה #2: {result}")
            _safe_run("free_learning_2", learn2)

        # 14:00 — למידה #3 (לפני KZ — חזרה על אסטרטגיה)
        elif h == 14 and m < 5 and not _once_today("learn_3"):
            def learn3():
                result = free_time_learning()
                print(f"[14:00] למידה #3 (pre-KZ review): {result}")
            _safe_run("free_learning_3", learn3)

        # 15:30 — בדיקה לפני KZ
        elif h == 15 and 30 <= m < 35 and not _once_today("pre_kz_check"):
            def pre_kz():
                events = get_today_events()
                print(f"[15:30] לפני KZ: {events.get('summary','')}")
                if events.get("during_kz"):
                    warn = f"HIGH IMPACT DURING KZ! Decision: {events.get('trading_decision')}"
                    print(f"[15:30] ⚠️ {warn}")
                    add_lesson(f"[אזהרה 15:30] {warn}", "risk_management")
                try:
                    from jimmy_web import jimmy_state
                    jimmy_state["today_events"] = events
                except Exception:
                    pass
            _safe_run("pre_kz_check", pre_kz)

        # 16:00 — תכנית סשן
        elif h == 16 and m < 5 and not _once_today("presession"):
            def do_presession():
                plan = presession_prep()
                try:
                    from jimmy_web import jimmy_state
                    jimmy_state["daily_plan"]   = plan
                    jimmy_state["today_events"] = get_today_events()
                except Exception:
                    pass
            _safe_run("presession_prep", do_presession)

        # 18:30 — סיכום סשן
        elif h == 18 and 30 <= m < 35 and not _once_today("postsession"):
            def do_postsession():
                review = postsession_review()
                try:
                    from jimmy_web import jimmy_state
                    jimmy_state["session_review"] = review
                except Exception:
                    pass
            _safe_run("postsession_review", do_postsession)

        # 19:30 — למידה #4 (ניתוח מה קרה בשוק היום)
        elif h == 19 and 30 <= m < 35 and not _once_today("learn_4"):
            def learn4():
                # לאחר KZ — לומד ממה שקרה בשוק היום
                today   = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d")
                results = _web_search(f"NQ futures recap analysis today {today}", max_results=5)
                insight = _extract_insight("NQ futures what happened today", results)
                if insight:
                    add_lesson(f"[ניתוח שוק {today}] {insight}", "market_recap")
                    print(f"[19:30] ניתוח שוק: {insight}")
                result = free_time_learning()
                print(f"[19:30] למידה #4: {result}")
            _safe_run("free_learning_4", learn4)

        # 21:00 — למידה #5
        elif h == 21 and m < 5 and not _once_today("learn_5"):
            def learn5():
                result = free_time_learning()
                stats  = get_learning_stats()
                print(f"[21:00] למידה #5: {result}")
                print(f"[21:00] סיכום למידה היום: {stats['learned_count']}/{stats['total_available']} נושאים ({stats['percentage']}%)")
            _safe_run("free_learning_5", learn5)

        time.sleep(60)


def start_research_scheduler():
    """הפעל research scheduler ב-background thread"""
    import threading
    t = threading.Thread(
        target=research_scheduler_loop,
        daemon=True,
        name="jimmy-research"
    )
    t.start()
    print("[Research] Scheduler פעיל — לוח יומי מלא")
    return t
