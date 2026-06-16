"""
scout.py — אסף: core scanning logic (no domain lock-in).

Each run: Asaf brainstorms a handful of diverse, currently-promising domains
(health, education, B2B SaaS, hobbies, local services, finance, etc.) himself,
avoiding domains he's already covered recently, then searches for real
complaints in each and proposes a product + pricing model per domain that
has a credible gap.

Usage:
    python scout.py            # creative run — Asaf picks the domains himself
    python scout.py "pets"     # forced run — scan one specific domain

Reuses the DDGS web search + Anthropic API pattern from
ninjatrader-mcp/jimmy_research.py, run on-demand rather than on a scheduler.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic
from ddgs import DDGS

ISRAEL_TZ = timezone(timedelta(hours=3))
DATA_DIR = Path(__file__).resolve().parent / "data"
REPORTS_DIR = DATA_DIR / "reports"
STATUS_FILE = DATA_DIR / "status.json"
EXPLORED_FILE = DATA_DIR / "explored_domains.json"

DOMAINS_PER_RUN = 4
QUERIES_PER_DOMAIN = 3


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))


def _web_search(query: str, max_results: int = 5) -> list[dict]:
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
                "name": "אסף",
                "status": status,
                "last_action": last_action,
                "timestamp": datetime.now(ISRAEL_TZ).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def get_explored_domains() -> list[str]:
    try:
        data = json.loads(EXPLORED_FILE.read_text(encoding="utf-8"))
        return data.get("domains", [])
    except Exception:
        return []


def _mark_explored(domains: list[str]) -> None:
    existing = get_explored_domains()
    for d in domains:
        if d not in existing:
            existing.append(d)
    # keep the list bounded so domains eventually become eligible again
    existing = existing[-40:]
    EXPLORED_FILE.write_text(
        json.dumps({"domains": existing, "updated_at": datetime.now(ISRAEL_TZ).isoformat()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def brainstorm_domains(n: int = DOMAINS_PER_RUN) -> list[dict]:
    """Ask Asaf to creatively pick N diverse domains + search queries for each."""
    explored = get_explored_domains()
    explored_text = ", ".join(explored[-20:]) or "(אף תחום עדיין)"

    prompt = f"""אתה אסף — סוכן שמחפש הזדמנויות עסקיות דיגיטליות. אתה יצירתי ופתוח-ראש,
לא נצמד לתחום אחד. המטרה: למצוא תחומים מגוונים שבהם יש כאב אמיתי וכדאי לבדוק.

תחומים שכבר נסקרו לאחרונה (השתדל להימנע מהם, אלא אם אין ברירה): {explored_text}

בחר {n} תחומים שונים מאוד אחד מהשני (לדוגמה: בריאות, חינוך, B2B SaaS, תחביבים/קהילות נישה,
שירותים מקומיים, פיננסים, פרודוקטיביות, הורות, חיות מחמד, נדל"ן, יצירתיות/אומנות) —
תחומים שנראים לך כדאיים *כרגע*, לא רק רעיונות כלליים.

עבור כל תחום, תן 3 שאילתות חיפוש בסטייל Reddit שיעלו תלונות/בקשות אמיתיות של אנשים.

ענה בפורמט הזה בדיוק, שורה לכל תחום:
DOMAIN: [שם תחום קצר] | QUERIES: [שאילתה 1] ;; [שאילתה 2] ;; [שאילתה 3]
"""
    response = _client().messages.create(
        model="claude-opus-4-8",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")

    domains = []
    for line in text.splitlines():
        m = re.match(r"DOMAIN:\s*(.+?)\s*\|\s*QUERIES:\s*(.+)", line.strip())
        if m:
            domain = m.group(1).strip()
            queries = [q.strip() for q in m.group(2).split(";;") if q.strip()]
            if domain and queries:
                domains.append({"domain": domain, "queries": queries[:QUERIES_PER_DOMAIN]})
    return domains


def run_scout(forced_domain: str | None = None) -> dict:
    now = datetime.now(ISRAEL_TZ)

    if forced_domain:
        print(f"[Scout] תחום מבוקש: {forced_domain}")
        _write_status("running", f"scanning {forced_domain} (forced)")
        domains = [{
            "domain": forced_domain,
            "queries": [
                f"reddit {forced_domain} frustrated wish there was a tool",
                f"reddit {forced_domain} paid too much complaint",
                f"reddit {forced_domain} missing feature need",
            ],
        }]
    else:
        print("[Scout] מתחיל סיעור מוחות על תחומים...")
        _write_status("running", "brainstorming domains")
        domains = brainstorm_domains()

    if not domains:
        _write_status("idle", "brainstorm failed — no domains")
        return {"error": "brainstorm produced no domains"}

    print(f"[Scout] תחומים שנבחרו: {', '.join(d['domain'] for d in domains)}")

    domain_snippets = {}
    for d in domains:
        snippets = []
        for q in d["queries"]:
            results = _web_search(q)
            print(f"[Scout] '{q}' -> {len(results)} תוצאות")
            for r in results[:4]:
                snippets.append(f"[{r.get('title', '')}]\n{r.get('body', '')[:350]}\nSource: {r.get('href', '')}")
        domain_snippets[d["domain"]] = snippets

    domains_block = "\n\n".join(
        f"=== תחום: {domain} ===\n" + ("\n\n".join(snips) if snips else "(לא נמצאו תוצאות)")
        for domain, snips in domain_snippets.items()
    )

    prompt = f"""אתה אסף — סוכן שמחפש הזדמנויות עסקיות. הנה מה שמצאת בכמה תחומים:

{domains_block}

לכל תחום, בדוק אם יש gap אמיתי שכדאי לבנות עליו מוצר. אם אין — אמור זאת בכנות, אל תמציא.
ענה בפורמט הזה בדיוק, לכל תחום עם gap אמיתי:

DOMAIN: [שם התחום]
PAIN_POINTS: [2-3 תלונות/בקשות אמיתיות, מופרדות ב- ;;]
GAP: [מה אין בשוק שאנשים מחפשים]
PRODUCT_IDEA: [שם + תיאור קונקרטי]
TARGET_AUDIENCE: [מי בדיוק]
PRICING_MODEL: [RETAINER $X/חודש או ONE_TIME $X + הסבר קצר]
WHY_NOW: [למה זה לא נפתר עדיין]
---
אם תחום לא הניב gap אמיתי, כתוב רק: DOMAIN: [שם] | NO_OPPORTUNITY: [הסבר קצר למה]
"""
    response = _client().messages.create(
        model="claude-opus-4-8",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    report_text = next((b.text for b in response.content if b.type == "text"), "")

    report = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "domains_explored": [d["domain"] for d in domains],
        "queries_used": {d["domain"]: d["queries"] for d in domains},
        "report": report_text,
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = REPORTS_DIR / f"{now.strftime('%Y-%m-%d_%H%M')}.json"
    out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    _mark_explored([d["domain"] for d in domains])
    _write_status("idle", f"completed scan: {', '.join(report['domains_explored'])} -> {out_file.name}")

    print(f"\n[Scout] דוח נכתב: {out_file}\n")
    print(report_text)
    return report


def get_latest_report() -> dict:
    try:
        files = sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


if __name__ == "__main__":
    forced = sys.argv[1] if len(sys.argv) > 1 else None
    run_scout(forced)
