#!/usr/bin/env python3
"""
Trading Dashboard - MNQ1! Live Analysis
Reads trade_log.json and prints full performance report
"""
import json, statistics
from datetime import datetime

LOG_FILE = r"C:\Users\DELL\New folder\trade_log.json"

def load():
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def dashboard():
    data   = load()
    acc    = data["account"]
    trades = data["trades"]

    wins   = [t for t in trades if t["outcome"] == "WIN"]
    losses = [t for t in trades if t["outcome"] == "LOSS"]
    bes    = [t for t in trades if t["outcome"] == "BREAKEVEN"]
    total  = len(trades)
    wr     = len(wins) / total * 100 if total else 0
    total_r   = sum(t["r"] for t in trades)
    total_pts = sum(t["pts"] for t in trades)
    total_usd = sum(t["pnl_usd"] for t in trades)

    # Equity curve
    eq, peak, max_dd = 0, 0, 0
    for t in trades:
        eq += t["r"]; peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)

    print()
    print("=" * 65)
    print("   TRADING DASHBOARD — MNQ1! (Micro E-mini Nasdaq-100)")
    print("=" * 65)
    print(f"\n  Account:    {acc['name']}")
    print(f"  Broker:     {acc['broker']}")
    print(f"  Point Value: ${acc['point_value']} per point per contract")

    print(f"\n  {'='*55}")
    print(f"  PERFORMANCE SUMMARY")
    print(f"  {'='*55}")
    print(f"  Total Trades:      {total}  ({len(wins)}W / {len(losses)}L / {len(bes)}BE)")
    print(f"  Win Rate:          {round(wr,1)}%")
    print(f"  Total R:           {round(total_r,2)}R")
    print(f"  Total Points:      {round(total_pts,1)} pts")
    print(f"  Total P&L:         ${round(total_usd,2)}")
    print(f"  Max Drawdown:      -{round(max_dd,1)}R")
    if wins:
        print(f"  Avg Win:           +{round(statistics.mean(t['pts'] for t in wins),1)} pts / +{round(statistics.mean(t['r'] for t in wins),2)}R")
    if losses:
        print(f"  Avg Loss:          -{round(statistics.mean(abs(t['pts']) for t in losses),1)} pts / -{round(statistics.mean(abs(t['r']) for t in losses),2)}R")
    if wins and losses:
        pf = sum(t['r'] for t in wins) / abs(sum(t['r'] for t in losses))
        print(f"  Profit Factor:     {round(pf,2)}")
        exp = (wr/100 * statistics.mean(t['r'] for t in wins)) - ((1-wr/100) * statistics.mean(abs(t['r']) for t in losses))
        print(f"  Expectancy:        {round(exp,2)}R per trade")

    print(f"\n  {'='*55}")
    print(f"  TRADE LOG")
    print(f"  {'='*55}")
    for t in trades:
        icon = "WIN " if t["outcome"]=="WIN" else ("LOSS" if t["outcome"]=="LOSS" else " BE ")
        sign = "+" if t["pts"] >= 0 else ""
        print(f"\n  [{t['id']}] {t['date']} | {t['session']}")
        print(f"      {t['direction']:<6} | Entry: {t['entry']} | SL: {t['sl']} | Exit: {t['exit']} ({t['exit_type']})")
        print(f"      Contracts: {t['contracts']} | Risk: {t['risk_pts']} pts | Result: {sign}{t['pts']} pts | {sign}{t['r']}R | ${sign}{t['pnl_usd']}")
        print(f"      Outcome: [{icon}] | Score: {t['setup']['score']}")
        print(f"      Setup: {t['setup']['trigger']}")
        print(f"      Confluence: {', '.join(t['setup']['confluence'][:3])}")

        m = t["management"]
        print(f"      BE Moved: {'YES' if m['be_moved'] else 'NO'} | Partials: {'YES' if m['partials_taken'] else 'NO'}")
        if m.get("mistake"):
            print(f"      *** MISTAKE: {m['mistake']}")
        if m.get("good_decision"):
            print(f"      *** GOOD: {m['good_decision']}")

    print(f"\n  {'='*55}")
    print(f"  LESSONS LEARNED")
    print(f"  {'='*55}")
    for t in trades:
        print(f"\n  Trade #{t['id']} ({t['direction']} {t['outcome']}):")
        print(f"    -> {t['lesson']}")

    print(f"\n  {'='*55}")
    print(f"  SESSION BREAKDOWN")
    print(f"  {'='*55}")
    for session in ["London Kill Zone", "NY AM Kill Zone"]:
        st = [t for t in trades if t["session"] == session]
        sw = [t for t in st if t["outcome"] == "WIN"]
        if st:
            s_r   = sum(t["r"] for t in st)
            s_pts = sum(t["pts"] for t in st)
            print(f"  {session:<22}: {len(st)} trades | {round(len(sw)/len(st)*100,0):.0f}% WR | {round(s_r,1):+}R | {round(s_pts,0):+.0f} pts")

    print(f"\n  {'='*55}")
    print(f"  KEY RULES (learned from today)")
    print(f"  {'='*55}")
    rules = [
        "1. Move SL to BE when price reaches 1R profit — NO EXCEPTIONS",
        "2. Take 35% partial at TP1, especially on counter-trend trades",
        "3. PSP/MES Clusters = strong reversal zones — respect as TP, not just targets",
        "4. London Kill Zone setups > NY AM setups in quality",
        "5. 5-min close below key level = exit signal",
        "6. Never fight the Directional Bias on full-size positions",
        "7. Score 7+/9 before entering — lower scores = smaller size"
    ]
    for r in rules:
        print(f"  {r}")

    print("\n" + "=" * 65)
    print(f"  Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

dashboard()
