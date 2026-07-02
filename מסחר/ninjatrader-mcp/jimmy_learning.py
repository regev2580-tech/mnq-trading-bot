"""
jimmy_learning.py — מערכת למידה אוטומטית של ג'ימי
════════════════════════════════════════════════════
כל עסקה → ניתוח → לקח → נשמר לצמיתות בjimmy_brain.json

מה ג'ימי לומד:
• למה הוא נכנס (ומה היה הרציונל)
• מה קרה בפועל (win/loss)
• מה היה קורה עם SL שונה
• מה היה קורה אם החזיק יותר
• איפה היה TP האמיתי של השוק
"""

import json
import threading
import time
import anthropic
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from jimmy_web import load_brain, add_lesson

ISRAEL_TZ  = timezone(timedelta(hours=3))
DATA_DIR   = Path(r"C:\Users\regev\New folder\ninjatrader-mcp\data")
JOURNAL    = DATA_DIR / "trade_journal.json"
POSITION   = DATA_DIR / "position.json"
ORDERFLOW  = DATA_DIR / "orderflow.json"

# כמה זמן לעקוב אחרי סגירת עסקה (לcounterfactuals)
POST_TRADE_TRACK_MINUTES = 45


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_journal() -> list:
    try:
        return json.loads(JOURNAL.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_journal(trades: list):
    JOURNAL.write_bytes(json.dumps(trades, ensure_ascii=False, indent=2).encode("utf-8"))


def _next_trade_id() -> str:
    trades = _load_journal()
    return f"T{len(trades) + 1}"


# ──────────────────────────────────────────────
# Trade Recorder — עוקב אחרי כל עסקה
# ──────────────────────────────────────────────

class TradeRecorder:
    """
    מתחיל לעקוב כשנשלח signal.
    מסיים ומנתח כשהפוזיציה נסגרת.
    ממשיך לעקוב 45 דקות אחרי סגירה (counterfactuals).
    """

    def __init__(self):
        self.active_trade: dict | None  = None
        self._lock   = threading.Lock()
        self._thread: threading.Thread | None = None

    def on_signal_sent(self, signal: dict, orderflow: dict,
                       tv_screenshot_path: str, reasoning: str):
        """קרא מיד אחרי שנשלח trade_signal.json"""
        with self._lock:
            bars = orderflow.get("bars", [])
            cvd  = sum(b.get("delta", 0) for b in bars)

            self.active_trade = {
                "id":               _next_trade_id(),
                "action":           signal.get("action"),
                "entry_price":      signal.get("entry", orderflow.get("price", 0)),
                "sl":               signal.get("sl", 0),
                "tp":               signal.get("tp", 0),
                "rr":               signal.get("rr", 0),
                "opened_at":        datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
                "entry_score":      orderflow.get("net_score", 0),
                "entry_cvd":        round(cvd, 0),
                "entry_delta":      orderflow.get("current_delta", 0),
                "entry_cdh":        orderflow.get("cdh", 0),
                "entry_cdl":        orderflow.get("cdl", 0),
                "entry_reasoning":  reasoning,
                "tv_screenshot":    tv_screenshot_path,
                "snapshots":        [],   # מחיר כל 2 דקות
                "post_snapshots":   [],   # מחיר 45 דקות אחרי סגירה
                "result":           None,
                "lesson":           None,
                "analysis":         None,
            }
            # הוסף snapshot ראשון
            self._add_snapshot(orderflow, "entry")

        # התחל מעקב ב-thread
        self._thread = threading.Thread(
            target=self._tracking_loop, daemon=True, name="trade-tracker"
        )
        self._thread.start()

    def _add_snapshot(self, of: dict, label: str = ""):
        if not self.active_trade:
            return
        bars = of.get("bars", [])
        cvd  = sum(b.get("delta", 0) for b in bars)
        snap = {
            "time":   datetime.now(ISRAEL_TZ).strftime("%H:%M:%S"),
            "price":  of.get("price"),
            "delta":  of.get("current_delta", 0),
            "cvd":    round(cvd, 0),
            "label":  label,
        }
        self.active_trade["snapshots"].append(snap)

    def _tracking_loop(self):
        """רץ כל 30 שניות, בודק אם פוזיציה נסגרה"""
        was_open = True

        while True:
            time.sleep(30)

            with self._lock:
                if not self.active_trade:
                    break

            of  = _read(ORDERFLOW)
            pos = _read(POSITION)

            if of:
                with self._lock:
                    self._add_snapshot(of)

            # בדוק אם פוזיציה נסגרה
            if pos and pos.get("status") == "flat" and was_open:
                with self._lock:
                    if self.active_trade:
                        self.active_trade["exit_price"] = pos.get("exit_price") or (of or {}).get("price")
                        self.active_trade["closed_at"]  = datetime.now(ISRAEL_TZ).strftime("%Y-%m-%d %H:%M:%S")
                was_open = False
                # עוד 45 דקות מעקב
                self._post_trade_tracking()
                break

            if pos and pos.get("status") == "open":
                was_open = True

    def _post_trade_tracking(self):
        """45 דקות מעקב אחרי סגירה — לcounterfactuals"""
        end_time = time.time() + POST_TRADE_TRACK_MINUTES * 60
        while time.time() < end_time:
            time.sleep(60)
            of = _read(ORDERFLOW)
            if of and self.active_trade:
                bars = of.get("bars", [])
                cvd  = sum(b.get("delta", 0) for b in bars)
                self.active_trade["post_snapshots"].append({
                    "time":  datetime.now(ISRAEL_TZ).strftime("%H:%M"),
                    "price": of.get("price"),
                    "delta": of.get("current_delta", 0),
                    "cvd":   round(cvd, 0),
                })

        # ניתוח מלא
        self._analyze_and_learn()

    def _analyze_and_learn(self):
        """הלב של המערכת — שולח לקלוד לניתוח מלא"""
        with self._lock:
            trade = dict(self.active_trade) if self.active_trade else None
            self.active_trade = None

        if not trade:
            return

        entry  = trade["entry_price"]
        sl     = trade["sl"]
        tp     = trade["tp"]
        exit_p = trade.get("exit_price", entry)
        action = trade["action"]   # BUY or SHORT

        # חשב P&L
        if action == "BUY":
            pnl = exit_p - entry
        else:
            pnl = entry - exit_p
        trade["pnl_pts"] = round(pnl, 2)

        # Counterfactuals מה-post_snapshots
        prices_after = [s["price"] for s in trade["post_snapshots"] if s.get("price")]

        cf = {}
        if prices_after:
            if action == "BUY":
                max_after   = max(prices_after)
                min_after   = min(prices_after)
                tp_hit      = max_after >= tp if tp else False
                sl15_survives = min_after > (entry - 15)
                sl25_survives = min_after > (entry - 25)
                max_profit  = max_after - entry
                held_30     = prices_after[min(29, len(prices_after)-1)] - entry
            else:
                max_after   = max(prices_after)
                min_after   = min(prices_after)
                tp_hit      = min_after <= tp if tp else False
                sl15_survives = max_after < (entry + 15)
                sl25_survives = max_after < (entry + 25)
                max_profit  = entry - min_after
                held_30     = entry - prices_after[min(29, len(prices_after)-1)]

            cf = {
                "tp_was_hit_after_close":   tp_hit,
                "max_profit_possible":      round(max_profit, 1),
                "sl_15pts_would_survive":   sl15_survives,
                "sl_25pts_would_survive":   sl25_survives,
                "pnl_if_held_30min":        round(held_30, 1),
                "pnl_if_held_45min":        round(
                    (prices_after[-1] - entry) if action == "BUY"
                    else (entry - prices_after[-1]), 1
                ) if prices_after else 0,
            }
        trade["counterfactuals"] = cf

        # שלח לקלוד לניתוח
        client  = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        outcome = "WIN" if pnl > 0 else ("BE" if pnl == 0 else "LOSS")

        prompt = f"""נתח עסקה זו ולמד ממנה לעסקאות הבאות.

עסקה: {trade['id']} | {action} | {outcome} | {pnl:+.1f} pts
═══════════════════════════════════════
כניסה: {entry} | SL: {sl} ({abs(entry-sl):.0f}pts) | TP: {tp} ({abs(tp-entry):.0f}pts)
סגירה: {exit_p} | P&L: {pnl:+.1f} pts

נתוני כניסה:
• Valtos Score: {trade['entry_score']:+d}
• CVD: {trade['entry_cvd']}
• Delta: {trade['entry_delta']:+d}
• Reasoning: {trade['entry_reasoning']}

מה קרה אחרי הסגירה ({POST_TRADE_TRACK_MINUTES} דקות):
{json.dumps(cf, ensure_ascii=False, indent=2)}

תנועת מחיר (snapshots):
{json.dumps([s for s in trade['post_snapshots'][:15]], ensure_ascii=False)}

ענה בפורמט זה בדיוק:
OUTCOME_REASON: [למה הצלחה/כשלון — משפט אחד]
ENTRY_QUALITY: [האם הכניסה היתה נכונה? GOOD/BAD/TIMING]
BIGGEST_MISTAKE: [הטעות הכי גדולה — אם יש]
COUNTERFACTUAL: [מה היה קורה אם {'' if not cf else ('SL 25pts' if not cf.get('sl_25pts_would_survive') else 'החזקת 30 דקות')}]
LESSON: [לקח אחד קצר וברור לעסקאות הבאות — משפט אחד]
RULE_TO_ADD: [האם צריך כלל חדש? כן/לא — אם כן, מה הכלל]
"""

        try:
            response = client.messages.create(
                model      = "claude-haiku-4-5",
                max_tokens = 600,
                messages   = [{"role": "user", "content": prompt}]
            )
            analysis = response.content[0].text.strip()
            trade["analysis"] = analysis

            # חלץ לקח
            for line in analysis.split("\n"):
                if line.startswith("LESSON:"):
                    lesson = line.replace("LESSON:", "").strip()
                    if lesson:
                        category = f"trade_{outcome.lower()}"
                        add_lesson(f"[{trade['id']} {outcome}] {lesson}", category)
                        trade["lesson"] = lesson

                if line.startswith("RULE_TO_ADD:") and "כן" in line:
                    rule_text = line.replace("RULE_TO_ADD:", "").strip()
                    add_lesson(f"[כלל חדש מ-{trade['id']}] {rule_text}", "new_rule")

        except Exception as e:
            trade["analysis"] = f"Error: {e}"

        # שמור ב-journal
        trades = _load_journal()
        trades.append(trade)
        _save_journal(trades)

        print(f"[{datetime.now(ISRAEL_TZ).strftime('%H:%M')}] "
              f"למידה מ-{trade['id']}: {trade.get('lesson', 'ללא לקח')}")


# singleton
recorder = TradeRecorder()
