#!/usr/bin/env python3
"""
ICT 2022 Backtest Engine - MNQ1!
Pure price action: Liquidity Sweeps, Kill Zones, Displacement, OTE
"""

import json
import subprocess
import sys
import statistics
from datetime import datetime, timezone

MCP_DIR = r"C:\Users\DELL\New folder\tradingview-mcp"

def run_cli(*args):
    result = subprocess.run(
        ["node", "src/cli/index.js"] + list(args),
        capture_output=True, text=True, cwd=MCP_DIR
    )
    return json.loads(result.stdout)

def set_timeframe(tf):
    run_cli("timeframe", "--set", str(tf))

def get_bars(resolution, count=500):
    set_timeframe(resolution)
    import time; time.sleep(2)
    data = run_cli("ohlcv", "--symbol", "CME_MINI:MNQ1!", "--count", str(count))
    return data.get("bars", [])

def is_kill_zone(ts):
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    h, m = dt.hour, dt.minute
    if 7 <= h < 10:                          return "London"
    if (h == 13 and m >= 30) or 14 <= h < 16: return "NY_AM"
    if (h == 18 and m >= 30) or 19 <= h < 21: return "NY_PM"
    return None

def atr(bars, period=14):
    trs = []
    for i in range(1, len(bars)):
        tr = max(
            bars[i]["high"] - bars[i]["low"],
            abs(bars[i]["high"] - bars[i-1]["close"]),
            abs(bars[i]["low"]  - bars[i-1]["close"])
        )
        trs.append(tr)
    if not trs: return 50
    return statistics.mean(trs[-period:])

def get_prev_day_levels(bars, idx, lookback_hours=24):
    """Get previous session high/low"""
    start = max(0, idx - lookback_hours)
    window = bars[start:idx]
    if not window: return None, None
    return max(b["high"] for b in window), min(b["low"] for b in window)

def is_displacement(bar, avg_atr, factor=1.3):
    """Large candle = displacement"""
    size = bar["high"] - bar["low"]
    body = abs(bar["close"] - bar["open"])
    return size > avg_atr * factor and body > size * 0.5

def run_backtest(bars_1h):
    avg_atr = atr(bars_1h)
    trades = []
    in_trade = False
    cooldown = 0

    for i in range(30, len(bars_1h) - 20):
        if cooldown > 0:
            cooldown -= 1
            continue

        bar = bars_1h[i]
        kz = is_kill_zone(bar["time"])
        if not kz:
            continue

        pdh, pdl = get_prev_day_levels(bars_1h, i, 24)
        if not pdh or not pdl:
            continue

        # Weekly high/low (last 5 days)
        pwh, pwl = get_prev_day_levels(bars_1h, i, 120)

        midpoint = (pdh + pdl) / 2

        # ──────────────────────────────────────────────
        # SHORT SETUP
        # Conditions:
        # 1. Price in premium (above midpoint)
        # 2. Bar sweeps PDH or PWH
        # 3. Closes back below the level (rejection)
        # 4. Displacement candle
        # ──────────────────────────────────────────────
        swept_high = pdh if bar["high"] > pdh else (pwh if pwh and bar["high"] > pwh else None)

        if (swept_high and
            bar["close"] < swept_high and
            bar["close"] < bar["open"] and
            bar["close"] > midpoint and
            is_displacement(bar, avg_atr)):

            # OTE entry: 50-62% retracement of displacement candle
            disp_range = bar["high"] - bar["close"]
            entry = bar["close"] + disp_range * 0.5
            sl    = bar["high"] + avg_atr * 0.15
            risk  = sl - entry

            if risk < 5 or risk > avg_atr * 3:
                continue

            # Targets
            tp1 = entry - risk * 2
            tp2 = entry - risk * 3
            tp3 = entry - risk * 4

            # Simulate forward
            result = simulate_trade(bars_1h, i, "SHORT", entry, sl, tp1, tp2, tp3)
            if result:
                result.update({
                    "kill_zone": kz,
                    "swept_level": round(swept_high, 2),
                    "entry_time": datetime.fromtimestamp(bar["time"]).strftime("%Y-%m-%d %H:%M"),
                    "risk_pts": round(risk, 1),
                    "atr": round(avg_atr, 1)
                })
                trades.append(result)
                cooldown = 6  # Wait 6 bars before next trade

        # ──────────────────────────────────────────────
        # LONG SETUP
        # Conditions:
        # 1. Price in discount (below midpoint)
        # 2. Bar sweeps PDL or PWL
        # 3. Closes back above the level
        # 4. Displacement candle
        # ──────────────────────────────────────────────
        swept_low = pdl if bar["low"] < pdl else (pwl if pwl and bar["low"] < pwl else None)

        if (swept_low and
            bar["close"] > swept_low and
            bar["close"] > bar["open"] and
            bar["close"] < midpoint and
            is_displacement(bar, avg_atr)):

            disp_range = bar["close"] - bar["low"]
            entry = bar["close"] - disp_range * 0.5
            sl    = bar["low"] - avg_atr * 0.15
            risk  = entry - sl

            if risk < 5 or risk > avg_atr * 3:
                continue

            tp1 = entry + risk * 2
            tp2 = entry + risk * 3
            tp3 = entry + risk * 4

            result = simulate_trade(bars_1h, i, "LONG", entry, sl, tp1, tp2, tp3)
            if result:
                result.update({
                    "kill_zone": kz,
                    "swept_level": round(swept_low, 2),
                    "entry_time": datetime.fromtimestamp(bar["time"]).strftime("%Y-%m-%d %H:%M"),
                    "risk_pts": round(risk, 1),
                    "atr": round(avg_atr, 1)
                })
                trades.append(result)
                cooldown = 6

    return trades

def simulate_trade(bars, setup_idx, direction, entry, sl, tp1, tp2, tp3):
    """Look ahead to see outcome"""
    entered = False
    max_bars = 20  # Max hold time

    for j in range(setup_idx + 1, min(setup_idx + max_bars, len(bars))):
        b = bars[j]

        # Check for entry fill (pullback)
        if not entered:
            if direction == "SHORT" and b["high"] >= entry:
                entered = True
            elif direction == "LONG" and b["low"] <= entry:
                entered = True
            else:
                continue

        if not entered:
            continue

        if direction == "SHORT":
            if b["high"] >= sl:
                return {"direction": "SHORT", "entry": round(entry,2), "sl": round(sl,2),
                        "exit": round(sl,2), "outcome": "LOSS", "r": -1.0}
            if b["low"] <= tp3:
                return {"direction": "SHORT", "entry": round(entry,2), "sl": round(sl,2),
                        "exit": round(tp3,2), "outcome": "WIN", "r": 4.0}
            if b["low"] <= tp2:
                return {"direction": "SHORT", "entry": round(entry,2), "sl": round(sl,2),
                        "exit": round(tp2,2), "outcome": "WIN", "r": 3.0}
            if b["low"] <= tp1:
                return {"direction": "SHORT", "entry": round(entry,2), "sl": round(sl,2),
                        "exit": round(tp1,2), "outcome": "WIN", "r": 2.0}

        else:  # LONG
            if b["low"] <= sl:
                return {"direction": "LONG", "entry": round(entry,2), "sl": round(sl,2),
                        "exit": round(sl,2), "outcome": "LOSS", "r": -1.0}
            if b["high"] >= tp3:
                return {"direction": "LONG", "entry": round(entry,2), "sl": round(sl,2),
                        "exit": round(tp3,2), "outcome": "WIN", "r": 4.0}
            if b["high"] >= tp2:
                return {"direction": "LONG", "entry": round(entry,2), "sl": round(sl,2),
                        "exit": round(tp2,2), "outcome": "WIN", "r": 3.0}
            if b["high"] >= tp1:
                return {"direction": "LONG", "entry": round(entry,2), "sl": round(sl,2),
                        "exit": round(tp1,2), "outcome": "WIN", "r": 2.0}

    # Trade expired without hitting SL or TP
    last = bars[min(setup_idx + max_bars, len(bars)-1)]
    close = last["close"]
    if direction == "SHORT":
        r = round((entry - close) / (sl - entry), 2)
    else:
        r = round((close - entry) / (entry - sl), 2)
    outcome = "WIN" if r > 0 else "LOSS"
    return {"direction": direction, "entry": round(entry,2), "sl": round(sl,2),
            "exit": round(close,2), "outcome": outcome, "r": r}

def print_report(trades):
    if not trades:
        print("לא נמצאו עסקאות")
        return

    total = len(trades)
    wins  = [t for t in trades if t["outcome"] == "WIN"]
    losses= [t for t in trades if t["outcome"] == "LOSS"]
    win_rate = len(wins) / total * 100
    total_r  = sum(t["r"] for t in trades)

    # Max drawdown
    running, peak, max_dd = 0, 0, 0
    for t in trades:
        running += t["r"]
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)

    # By Kill Zone
    kz_data = {}
    for kz in ["London", "NY_AM", "NY_PM"]:
        kt = [t for t in trades if t.get("kill_zone") == kz]
        if kt:
            kw = [t for t in kt if t["outcome"] == "WIN"]
            kz_data[kz] = f"{len(kt)} עסקאות | {round(len(kw)/len(kt)*100,1)}% ניצחון | {round(sum(t['r'] for t in kt),1)}R"

    # By direction
    longs  = [t for t in trades if t["direction"] == "LONG"]
    shorts = [t for t in trades if t["direction"] == "SHORT"]
    lw = [t for t in longs  if t["outcome"] == "WIN"]
    sw = [t for t in shorts if t["outcome"] == "WIN"]

    print("\n" + "="*55)
    print("   ICT BACKTEST — MNQ1! | 6 חודשים אחרונים")
    print("="*55)
    print(f"\n  סה\"כ עסקאות:      {total}")
    print(f"  ניצחונות:          {len(wins)}  ({round(win_rate,1)}%)")
    print(f"  הפסדים:            {len(losses)}")
    print(f"  סה\"כ R:            {round(total_r,1)}R")
    print(f"  ממוצע R לעסקה:     {round(total_r/total,2)}R")
    if wins:
        print(f"  ממוצע R על ניצחון: {round(statistics.mean(t['r'] for t in wins),2)}R")
    print(f"  Max Drawdown:      -{round(max_dd,1)}R")

    print(f"\n  LONG:  {len(longs)} עסקאות | {round(len(lw)/len(longs)*100,1) if longs else 0}% ניצחון")
    print(f"  SHORT: {len(shorts)} עסקאות | {round(len(sw)/len(shorts)*100,1) if shorts else 0}% ניצחון")

    print("\n  לפי Kill Zone:")
    for kz, stat in kz_data.items():
        print(f"    {kz}: {stat}")

    print("\n  10 עסקאות אחרונות:")
    print(f"  {'תאריך':<17} {'כיוון':<6} {'כניסה':<8} {'תוצאה':<6} {'R'}")
    print("  " + "-"*48)
    for t in trades[-10:]:
        icon = "✅" if t["outcome"] == "WIN" else "❌"
        print(f"  {t.get('entry_time',''):<17} {t['direction']:<6} {t['entry']:<8} {icon} {t['r']:+.1f}R")

    print("\n" + "="*55)

# ─── MAIN ───────────────────────────────────────────
print("מושך נתונים היסטוריים (4H)...")
bars_4h = get_bars(240, 500)
print(f"קיבלתי {len(bars_4h)} נרות של 4 שעות")

if len(bars_4h) < 50:
    print("מנסה 1H...")
    bars_4h = get_bars(60, 500)
    print(f"קיבלתי {len(bars_4h)} נרות של שעה")

print("מריץ backtest ICT...")
trades = run_backtest(bars_4h)
print_report(trades)
