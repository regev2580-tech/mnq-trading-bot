#!/usr/bin/env python3
"""
ICT 2022 Backtest Engine - MNQ1! - Daily Bars
Pure Price Action: Liquidity Sweeps, Premium/Discount, Market Structure
"""
import json, subprocess, statistics, sys
from datetime import datetime, timezone, timedelta

MCP_DIR = r"C:\Users\DELL\New folder\tradingview-mcp"

def get_bars():
    r = subprocess.run(
        ["node","src/cli/index.js","ohlcv","--symbol","CME_MINI:MNQ1!","--count","300"],
        capture_output=True, text=True, cwd=MCP_DIR
    )
    return json.loads(r.stdout).get("bars", [])

def atr(bars, n=14):
    trs = [max(bars[i]["high"]-bars[i]["low"],
               abs(bars[i]["high"]-bars[i-1]["close"]),
               abs(bars[i]["low"]-bars[i-1]["close"]))
           for i in range(1,len(bars))]
    return statistics.mean(trs[-n:]) if trs else 50

def weekly_hl(bars, idx):
    """Previous 5 trading days high/low"""
    w = bars[max(0,idx-5):idx]
    return max(b["high"] for b in w), min(b["low"] for b in w)

def monthly_hl(bars, idx):
    """Previous 20 trading days high/low"""
    m = bars[max(0,idx-20):idx]
    return max(b["high"] for b in m), min(b["low"] for b in m)

def mss(bars, idx, direction):
    """Market Structure Shift - checks if structure broke"""
    if idx < 3: return False
    if direction == "BEAR":
        # Previous 3 bars made higher highs?
        recent_highs = [bars[idx-k]["high"] for k in range(1,4)]
        return bars[idx]["close"] < min(bars[idx-1]["low"], bars[idx-2]["low"])
    else:
        recent_lows = [bars[idx-k]["low"] for k in range(1,4)]
        return bars[idx]["close"] > max(bars[idx-1]["high"], bars[idx-2]["high"])

def run_backtest(bars):
    avg_atr = atr(bars)
    trades = []
    # Filter to last 6 months
    cutoff = datetime(2025,11,1, tzinfo=timezone.utc).timestamp()

    for i in range(25, len(bars)-3):
        bar = bars[i]
        if bar["time"] < cutoff:
            continue

        date_str = datetime.fromtimestamp(bar["time"]).strftime("%Y-%m-%d")

        pdh = bars[i-1]["high"]   # Previous Day High
        pdl = bars[i-1]["low"]    # Previous Day Low
        pdc = bars[i-1]["close"]  # Previous Day Close

        pwh, pwl = weekly_hl(bars, i)
        pmh, pml = monthly_hl(bars, i)

        day_range = pdh - pdl
        midpoint  = pdl + day_range * 0.5

        # ATR for this period
        local_atr = atr(bars[max(0,i-20):i+1])

        # ── SHORT SETUP ──────────────────────────────────
        # 1. Day sweeps PDH or weekly high
        # 2. Closes back below it = rejection / manipulation
        # 3. Day closes bearish
        swept_high = None
        if bar["high"] > pdh and bar["close"] < pdh:
            swept_high = pdh
        elif bar["high"] > pwh and bar["close"] < pwh:
            swept_high = pwh

        if swept_high and bar["close"] < bar["open"]:
            # Are we in premium? (close above midpoint of last week range)
            in_premium = bar["close"] > (pwh + pwl) / 2

            # ICT OTE Entry: 50% of today's range (sell into discount of displacement)
            sweep_size = bar["high"] - bar["close"]
            entry = bar["close"] + sweep_size * 0.5

            # SL: above the sweep high + 15% ATR buffer
            sl   = bar["high"] + local_atr * 0.15
            risk = sl - entry

            if risk < local_atr * 0.3 or risk > local_atr * 2:
                continue

            # Targets
            tp1 = entry - risk * 2    # 2R
            tp2 = entry - risk * 3    # 3R
            tp3 = entry - risk * 4    # 4R

            # Target levels (previous swing lows)
            prev_lows = [bars[i-k]["low"] for k in range(1,6)]
            structural_target = min(prev_lows)

            # Simulate on next bars
            outcome = simulate(bars, i, "SHORT", entry, sl, tp1, tp2, tp3, max_bars=10)
            if outcome:
                outcome.update({
                    "date": date_str,
                    "direction": "SHORT",
                    "swept": round(swept_high,2),
                    "entry": round(entry,2),
                    "sl": round(sl,2),
                    "in_premium": in_premium,
                    "risk_pts": round(risk,1),
                    "target_structural": round(structural_target,2)
                })
                trades.append(outcome)

        # ── LONG SETUP ───────────────────────────────────
        # 1. Day sweeps PDL or weekly low
        # 2. Closes back above it
        # 3. Day closes bullish
        swept_low = None
        if bar["low"] < pdl and bar["close"] > pdl:
            swept_low = pdl
        elif bar["low"] < pwl and bar["close"] > pwl:
            swept_low = pwl

        if swept_low and bar["close"] > bar["open"]:
            in_discount = bar["close"] < (pwh + pwl) / 2

            sweep_size = bar["close"] - bar["low"]
            entry = bar["close"] - sweep_size * 0.5

            sl   = bar["low"] - local_atr * 0.15
            risk = entry - sl

            if risk < local_atr * 0.3 or risk > local_atr * 2:
                continue

            tp1 = entry + risk * 2
            tp2 = entry + risk * 3
            tp3 = entry + risk * 4

            prev_highs = [bars[i-k]["high"] for k in range(1,6)]
            structural_target = max(prev_highs)

            outcome = simulate(bars, i, "LONG", entry, sl, tp1, tp2, tp3, max_bars=10)
            if outcome:
                outcome.update({
                    "date": date_str,
                    "direction": "LONG",
                    "swept": round(swept_low,2),
                    "entry": round(entry,2),
                    "sl": round(sl,2),
                    "in_discount": in_discount,
                    "risk_pts": round(risk,1),
                    "target_structural": round(structural_target,2)
                })
                trades.append(outcome)

    return trades

def simulate(bars, setup_idx, direction, entry, sl, tp1, tp2, tp3, max_bars=10):
    filled = False
    risk = abs(sl - entry)
    for j in range(setup_idx+1, min(setup_idx+max_bars, len(bars))):
        b = bars[j]
        if not filled:
            if b["low"] <= entry <= b["high"]:
                filled = True
            else:
                continue
        if direction == "SHORT":
            if b["high"] >= sl:
                return {"outcome":"LOSS","r":-1.0,"exit":round(sl,2)}
            if b["low"] <= tp3:
                return {"outcome":"WIN","r":4.0,"exit":round(tp3,2)}
            if b["low"] <= tp2:
                return {"outcome":"WIN","r":3.0,"exit":round(tp2,2)}
            if b["low"] <= tp1:
                return {"outcome":"WIN","r":2.0,"exit":round(tp1,2)}
        else:
            if b["low"] <= sl:
                return {"outcome":"LOSS","r":-1.0,"exit":round(sl,2)}
            if b["high"] >= tp3:
                return {"outcome":"WIN","r":4.0,"exit":round(tp3,2)}
            if b["high"] >= tp2:
                return {"outcome":"WIN","r":3.0,"exit":round(tp2,2)}
            if b["high"] >= tp1:
                return {"outcome":"WIN","r":2.0,"exit":round(tp1,2)}

    # Expired - close at last bar
    if not filled:
        return None
    last = bars[min(setup_idx+max_bars, len(bars)-1)]
    r = (entry - last["close"]) / risk if direction=="SHORT" else (last["close"] - entry) / risk
    return {"outcome":"WIN" if r>0 else "LOSS","r":round(r,2),"exit":round(last["close"],2)}

def report(trades):
    if not trades:
        print("No trades found. Check data."); return

    wins   = [t for t in trades if t["outcome"]=="WIN"]
    losses = [t for t in trades if t["outcome"]=="LOSS"]
    total  = len(trades)
    wr     = len(wins)/total*100
    total_r= sum(t["r"] for t in trades)

    # Drawdown
    eq, peak, max_dd = 0,0,0
    for t in trades:
        eq += t["r"]; peak = max(peak,eq); max_dd = max(max_dd, peak-eq)

    # Streaks
    streak, best_streak, worst_streak, cur_streak = 0,0,0,0
    last_outcome = None
    for t in trades:
        if t["outcome"] == last_outcome:
            cur_streak += 1
        else:
            cur_streak = 1
        if t["outcome"]=="WIN": best_streak = max(best_streak, cur_streak)
        else: worst_streak = max(worst_streak, cur_streak)
        last_outcome = t["outcome"]

    longs  = [t for t in trades if t["direction"]=="LONG"]
    shorts = [t for t in trades if t["direction"]=="SHORT"]
    lw = [t for t in longs  if t["outcome"]=="WIN"]
    sw = [t for t in shorts if t["outcome"]=="WIN"]

    # R distribution
    r2 = len([t for t in wins if t["r"]>=2])
    r3 = len([t for t in wins if t["r"]>=3])
    r4 = len([t for t in wins if t["r"]>=4])

    print()
    print("="*58)
    print("   ICT BACKTEST RESULTS - MNQ1!")
    print("   Nov 2025 - May 2026 (6 months)")
    print("="*58)
    print(f"\n  Total Trades:       {total}")
    print(f"  Wins:               {len(wins)}  ({round(wr,1)}%)")
    print(f"  Losses:             {len(losses)}")
    print(f"  Total R:            {round(total_r,1)}R")
    print(f"  Avg R per trade:    {round(total_r/total,2)}R")
    if wins:
        print(f"  Avg R on wins:      {round(statistics.mean(t['r'] for t in wins),2)}R")
    print(f"  Max Drawdown:       -{round(max_dd,1)}R")
    print(f"  Best win streak:    {best_streak}")
    print(f"  Worst loss streak:  {worst_streak}")
    print(f"\n  Win Distribution:")
    print(f"    2R+ wins: {r2}   |  3R+ wins: {r3}   |  4R wins: {r4}")
    print(f"\n  By Direction:")
    print(f"    LONG:  {len(longs)} trades | {round(len(lw)/len(longs)*100,1) if longs else 0}% WR | {round(sum(t['r'] for t in longs),1)}R total")
    print(f"    SHORT: {len(shorts)} trades | {round(len(sw)/len(shorts)*100,1) if shorts else 0}% WR | {round(sum(t['r'] for t in shorts),1)}R total")

    print("\n  All Trades:")
    print(f"  {'Date':<12} {'Dir':<6} {'Entry':<8} {'Exit':<8} {'R':>5}  Result")
    print("  " + "-"*52)
    for t in trades:
        icon = "WIN " if t["outcome"]=="WIN" else "LOSS"
        print(f"  {t['date']:<12} {t['direction']:<6} {t['entry']:<8} {t['exit']:<8} {t['r']:>+5.1f}  {icon}")

    print("\n" + "="*58)
    # Expectancy
    if wins and losses:
        avg_win  = statistics.mean(t["r"] for t in wins)
        avg_loss = abs(statistics.mean(t["r"] for t in losses))
        expectancy = (wr/100 * avg_win) - ((1-wr/100) * avg_loss)
        print(f"  Expectancy per trade: {round(expectancy,2)}R")
        if expectancy > 0:
            print(f"  -> PROFITABLE SYSTEM")
        else:
            print(f"  -> SYSTEM NEEDS IMPROVEMENT")
    print("="*58)

import time as _time

print("Setting chart to Daily timeframe...")
subprocess.run(["node","src/cli/index.js","timeframe","--set","D"],
               capture_output=True, text=True, cwd=MCP_DIR)
_time.sleep(4)

print("Pulling daily bars...")
bars = get_bars()
print(f"Got {len(bars)} daily bars")

# Verify daily (gap > 60000s)
if len(bars) > 2:
    gap = bars[1]["time"] - bars[0]["time"]
    if gap < 60000:
        print(f"ERROR: bars are {gap}s apart - not daily! Abort.")
        sys.exit(1)
    from datetime import datetime
    print(f"Date range: {datetime.fromtimestamp(bars[0]['time']).strftime('%Y-%m-%d')} -> {datetime.fromtimestamp(bars[-1]['time']).strftime('%Y-%m-%d')}")

print("Running ICT backtest (Nov 2025 - May 2026)...")
trades = run_backtest(bars)
report(trades)
