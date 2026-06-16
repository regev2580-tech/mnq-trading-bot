"""
scout.py — Business Scout: on-demand market-gap scanner.

Usage:
    python scout.py [niche]

Scans forums/Reddit-style discussion for recurring complaints in a niche,
then asks Claude to turn the raw complaints into one concrete product idea
with a pricing model (retainer or one-time). Same search+analyze pattern as
ninjatrader-mcp/jimmy_research.py (DDGS web search + Anthropic API), but
run on-demand instead of on a 24/7 scheduler.
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic
from ddgs import DDGS

ISRAEL_TZ = timezone(timedelta(hours=3))
DATA_DIR = Path(__file__).resolve().parent / "data"
REPORTS_DIR = DATA_DIR / "reports"
STATUS_FILE = DATA_DIR / "status.json"

NICHE_QUERIES = {
    "finance": [
        "reddit r/daytrading frustrated trade journal app complaint",
        "reddit prop firm evaluation tool wish there was",
        "reddit futures trading bot scam expensive alternative",
        "reddit day trading discord community worth the money",
        "reddit trading risk management tool missing feature",
        "reddit retail trader paid for mentor course regret",
    ],
}


def _web_search(query: str, max_results: int = 6) -> list[dict]:
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        print(f"[Scout] search error: {e}")
        return []


def _write_status(status: str, last_action: str) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(
        json.dumps(
            {
                "name": "Business Scout",
                "status": status,
                "last_action": last_action,
                "timestamp": datetime.now(ISRAEL_TZ).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def run_scout(niche_key: str = "finance") -> dict:
    now = datetime.now(ISRAEL_TZ)
    queries = NICHE_QUERIES.get(niche_key, NICHE_QUERIES["finance"])
    print(f"[Scout] סורק תחום: {niche_key} | {len(queries)} שאילתות")
    _write_status("running", f"scanning {niche_key}")

    all_snippets = []
    for q in queries:
        results = _web_search(q)
        print(f"[Scout] '{q}' -> {len(results)} תוצאות")
        for r in results[:4]:
            all_snippets.append(
                f"[{r.get('title', '')}]\n{r.get('body', '')[:400]}\nSource: {r.get('href', '')}"
            )

    if not all_snippets:
        _write_status("idle", "no results found")
        return {"error": "no search results"}

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    snippets_text = "\n\n".join(all_snippets[:25])

    prompt = f"""אתה Business Scout — סוכן שמחפש הזדמנויות עסקיות אמיתיות ברשת.
תחום: {niche_key}

מה שמצאתי ברשת (תלונות/בקשות אמיתיות):
{snippets_text}

מצא gap אחד אמיתי וקונקרטי, והצע מוצר דיגיטלי ספציפי שפותר אותו. ענה בפורמט הזה בדיוק:

PAIN_POINTS:
• [תלונה/בקשה חוזרת 1]
• [תלונה/בקשה חוזרת 2]
• [תלונה/בקשה חוזרת 3]

GAP: [הסבר קצר — מה אין בשוק שאנשים מחפשים]

PRODUCT_IDEA: [שם + תיאור קונקרטי של המוצר — משפט או שניים]

TARGET_AUDIENCE: [מי בדיוק הקונה]

PRICING_MODEL: [RETAINER $X/חודש או ONE_TIME $X — עם הסבר קצר למה זה המודל הנכון]

WHY_NOW: [למה זה gap אמיתי ולא נפתר כבר]

MVP_NEXT_STEP: [הצעד הקטן ביותר לבדוק את הרעיון בשבוע אחד]
"""

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    report_text = next((b.text for b in response.content if b.type == "text"), "")

    report = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "niche": niche_key,
        "queries": queries,
        "report": report_text,
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = REPORTS_DIR / f"{now.strftime('%Y-%m-%d_%H%M')}.json"
    out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    _write_status("idle", f"completed scan: {niche_key} -> {out_file.name}")
    print(f"[Scout] דוח נכתב: {out_file}\n")
    print(report_text)
    return report


if __name__ == "__main__":
    niche = sys.argv[1] if len(sys.argv) > 1 else "finance"
    run_scout(niche)
