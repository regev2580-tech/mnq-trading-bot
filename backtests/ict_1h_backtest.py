#!/usr/bin/env python3
"""
ICT 1H Historical Analysis — MNQ1!
Kill Zone setups: London + NY AM
Shows every trade with entry/SL/TP/outcome + points won/lost
"""
import json, sys, statistics
from datetime import datetime, timezone, timedelta

DATA_FILE = r"C:\Users\DELL\.claude\projects\c--Users-DELL-New-folder\74a98524-849f-42d9-804f-d413c554c8fe\tool-results\bk2qttcd1.txt"

def load_bars():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw = f.read()
    # Find the JSON part
    start = raw.find("{")
    data = json.loads(raw[start:])
    return data["bars"]

def kill_zone(ts):
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    h, m = dt.hour, dt.minute
    # London: 07:00-10:00 UTC
    if 7 <= h < 10:
        return "London"
    # NY AM: 13:30-16:00 UTC
    if (h == 13 and m >= 30) or (14 <= h < 16):
        return "NY_AM"
    return None

def atr(bars, n=14):
    trs = [max(bars[i]["high"] - bars[i]["low"],
               abs(bars[i]["high"] - bars[i-1]["close"]),
               abs(bars[i]["low"]  - bars[i-1]["close"]))
           for i in range(1, len(bars))]
    return statistics.mean(trs[-n:]) if trs else 50

def session_hl(bars, idx, hours=8):
    """Previous session high/low"""
    w = bars[max(0, idx - hours):idx]
    if not w: return None, None
    return max(b["high"] for b in w), min(b["low"] for b in w)

def is_displacement(bar, avg_atr, factor=1.2):
    size = bar["high"] - bar["low"]
    body = abs(bar["close"] - bar["open"])
    return size > avg_atr * factor and body > size * 0.45

def simulate(bars, idx, direction, entry, sl, tp1, tp2, tp3, max_bars=12):
    filled = False
    risk = abs(sl - entry)
    for j in range(idx + 1, min(idx + max_bars, len(bars))):
        b = bars[j]
        if not filled:
            if direction == "SHORT" and b["high"] >= entry:
                filled = True
            elif direction == "LONG" and b["low"] <= entry:
                filled = True
            else:
                continue
        if direction == "SHORT":
            if b["high"] >= sl:
                return {"r": -1.0, "outcome": "LOSS", "pts": round(-risk, 1), "exit": sl}
            if b["low"] <= tp3:
                return {"r": 4.0, "outcome": "WIN",  "pts": round(risk * 4, 1), "exit": tp3}
            if b["low"] <= tp2:
                return {"r": 3.0, "outcome": "WIN",  "pts": round(risk * 3, 1), "exit": tp2}
            if b["low"] <= tp1:
                return {"r": 2.0, "outcome": "WIN",  "pts": round(risk * 2, 1), "exit": tp1}
        else:
            if b["low"] <= sl:
                return {"r": -1.0, "outcome": "LOSS", "pts": round(-risk, 1), "exit": sl}
            if b["high"] >= tp3:
                return {"r": 4.0, "outcome": "WIN",  "pts": round(risk * 4, 1), "exit": tp3}
            if b["high"] >= tp2:
                return {"r": 3.0, "outcome": "WIN",  "pts": round(risk * 3, 1), "exit": tp2}
            if b["high"] >= tp1:
                return {"r": 2.0, "outcome": "WIN",  "pts": round(risk * 2, 1), "exit": tp1}
    if not filled:
        return None
    last = bars[min(idx + max_bars, len(bars) - 1)]
    r = (entry - last["close"]) / risk if direction == "SHORT" else (last["close"] - entry) / risk
    pts = risk * r
    return {"r": round(r, 2), "outcome": "WIN" if r > 0 else "LOSS",
            "pts": round(pts, 1), "exit": last["close"]}

def run():
    bars = load_bars()
    avg_atr = atr(bars)
    trades = []
    cooldown = 0

    for i in range(24, len(bars) - 15):
        if cooldown > 0:
            cooldown -= 1
            continue

        bar = bars[i]
        kz = kill_zone(bar["time"])
        if not kz:
            continue

        local_atr = atr(bars[max(0, i-20):i+1])
        pdh, pdl = session_hl(bars, i, 8)
        pwh, pwl = session_hl(bars, i, 24)  # prev day
        if not pdh: continue

        midpoint = (pdh + pdl) / 2

        # ── SHORT ──
        swept_high = None
        if bar["high"] > pdh and bar["close"] < pdh:
            swept_high = pdh
        elif pwh and bar["high"] > pwh and bar["close"] < pwh:
            swept_high = pwh

        if swept_high and bar["close"] < bar["open"] and is_displacement(bar, local_atr):
            sweep_range = bar["high"] - bar["close"]
            entry = bar["close"] + sweep_range * 0.618
            sl    = bar["high"] + local_atr * 0.12
            risk  = sl - entry
            if local_atr * 0.2 < risk < local_atr * 2.5:
                tp1 = entry - risk * 2
                tp2 = entry - risk * 3
                tp3 = entry - risk * 4
                result = simulate(bars, i, "SHORT", entry, sl, tp1, tp2, tp3)
                if result:
                    dt = datetime.fromtimestamp(bar["time"], tz=timezone.utc)
                    trades.append({
                        "date":    dt.strftime("%Y-%m-%d"),
                        "time_utc": dt.strftime("%H:%M"),
                        "time_il":  (dt + timedelta(hours=3)).strftime("%H:%M"),
                        "kz":      kz,
                        "dir":     "SHORT",
                        "entry":   round(entry, 2),
                        "sl":      round(sl, 2),
                        "tp1":     round(tp1, 2),
                        "tp2":     round(tp2, 2),
                        "swept":   round(swept_high, 2),
                        "risk_pts": round(risk, 1),
                        **result
                    })
                    cooldown = 8

        # ── LONG ──
        swept_low = None
        if bar["low"] < pdl and bar["close"] > pdl:
            swept_low = pdl
        elif pwl and bar["low"] < pwl and bar["close"] > pwl:
            swept_low = pwl

        if swept_low and bar["close"] > bar["open"] and is_displacement(bar, local_atr):
            sweep_range = bar["close"] - bar["low"]
            entry = bar["close"] - sweep_range * 0.618
            sl    = bar["low"] - local_atr * 0.12
            risk  = entry - sl
            if local_atr * 0.2 < risk < local_atr * 2.5:
                tp1 = entry + risk * 2
                tp2 = entry + risk * 3
                tp3 = entry + risk * 4
                result = simulate(bars, i, "LONG", entry, sl, tp1, tp2, tp3)
                if result:
                    dt = datetime.fromtimestamp(bar["time"], tz=timezone.utc)
                    trades.append({
                        "date":    dt.strftime("%Y-%m-%d"),
                        "time_utc": dt.strftime("%H:%M"),
                        "time_il":  (dt + timedelta(hours=3)).strftime("%H:%M"),
                        "kz":      kz,
                        "dir":     "LONG",
                        "entry":   round(entry, 2),
                        "sl":      round(sl, 2),
                        "tp1":     round(tp1, 2),
                        "tp2":     round(tp2, 2),
                        "swept":   round(swept_low, 2),
                        "risk_pts": round(risk, 1),
                        **result
                    })
                    cooldown = 8

    return trades

def report(trades):
    if not trades:
        print("No trades found."); return

    wins   = [t for t in trades if t["outcome"] == "WIN"]
    losses = [t for t in trades if t["outcome"] == "LOSS"]
    total  = len(trades)
    wr     = len(wins) / total * 100
    total_r = sum(t["r"] for t in trades)
    total_pts = sum(t["pts"] for t in trades)

    # By Kill Zone
    for kz in ["London", "NY_AM"]:
        kt = [t for t in trades if t["kz"] == kz]
        kw = [t for t in kt if t["outcome"] == "WIN"]
        if kt:
            kz_wr  = len(kw) / len(kt) * 100
            kz_r   = sum(t["r"] for t in kt)
            kz_pts = sum(t["pts"] for t in kt)

    # Max DD
    eq, peak, max_dd = 0, 0, 0
    for t in trades:
        eq += t["r"]; peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)

    print()
    print("=" * 70)
    print("   ICT 1H HISTORICAL ANALYSIS — MNQ1!  |  Kill Zone Setups")
    print("=" * 70)
    print(f"\n  Data range: {trades[0]['date']} -> {trades[-1]['date']}")
    print(f"  Total Trades:     {total}")
    print(f"  Win Rate:         {round(wr, 1)}%  ({len(wins)}W / {len(losses)}L)")
    print(f"  Total R:          {round(total_r, 1)}R")
    print(f"  Total Points:     {round(total_pts, 0)} pts")
    if wins:
        avg_win_pts = statistics.mean(t["pts"] for t in wins)
        print(f"  Avg Win:          +{round(avg_win_pts, 0)} pts")
    if losses:
        avg_loss_pts = statistics.mean(abs(t["pts"]) for t in losses)
        print(f"  Avg Loss:         -{round(avg_loss_pts, 0)} pts")
    print(f"  Max Drawdown:     -{round(max_dd, 1)}R")

    print(f"\n  BY KILL ZONE:")
    for kz in ["London", "NY_AM"]:
        kt = [t for t in trades if t["kz"] == kz]
        kw = [t for t in kt if t["outcome"] == "WIN"]
        if kt:
            print(f"    {kz:<8}: {len(kt):>3} trades | {round(len(kw)/len(kt)*100,1):>5}% WR | "
                  f"{round(sum(t['r'] for t in kt),1):>5}R | "
                  f"{round(sum(t['pts'] for t in kt),0):>6} pts")

    print(f"\n  BY DIRECTION:")
    for d in ["LONG", "SHORT"]:
        dt_ = [t for t in trades if t["dir"] == d]
        dw  = [t for t in dt_ if t["outcome"] == "WIN"]
        if dt_:
            print(f"    {d:<6}: {len(dt_):>3} trades | {round(len(dw)/len(dt_)*100,1):>5}% WR | "
                  f"{round(sum(t['r'] for t in dt_),1):>5}R")

    print(f"\n  BY HOUR (UTC+3 Israel time):")
    hours = {}
    for t in trades:
        h = t["time_il"][:2]
        hours.setdefault(h, []).append(t)
    for h in sorted(hours.keys()):
        ht = hours[h]; hw = [t for t in ht if t["outcome"] == "WIN"]
        print(f"    {h}:00  {len(ht):>3} trades | {round(len(hw)/len(ht)*100,1):>5}% WR | "
              f"{round(sum(t['r'] for t in ht),1):>+5}R")

    print(f"\n  R DISTRIBUTION (wins):")
    r2 = len([t for t in wins if t["r"] >= 2])
    r3 = len([t for t in wins if t["r"] >= 3])
    r4 = len([t for t in wins if t["r"] >= 4])
    print(f"    2R+ : {r2}  |  3R+ : {r3}  |  4R : {r4}")

    print(f"\n  ALL TRADES:")
    print(f"  {'Date':<12} {'IL':<6} {'KZ':<8} {'Dir':<6} {'Entry':<9} {'SL':<9} {'Risk':>5} {'Pts':>7}  {'R':>5}  Result")
    print("  " + "-" * 72)
    for t in trades:
        icon = "WIN " if t["outcome"] == "WIN" else "LOSS"
        sign = "+" if t["pts"] > 0 else ""
        print(f"  {t['date']:<12} {t['time_il']:<6} {t['kz']:<8} {t['dir']:<6} "
              f"{t['entry']:<9} {t['sl']:<9} {t['risk_pts']:>5} "
              f"{sign}{t['pts']:>6}pts  {t['r']:>+5.1f}  {icon}")

    print("\n" + "=" * 70)
    if wins and losses:
        avg_w = statistics.mean(t["r"] for t in wins)
        avg_l = abs(statistics.mean(t["r"] for t in losses))
        exp = (wr/100 * avg_w) - ((1 - wr/100) * avg_l)
        print(f"  Expectancy: {round(exp, 2)}R per trade")
        pf = sum(t["r"] for t in wins) / abs(sum(t["r"] for t in losses))
        print(f"  Profit Factor: {round(pf, 2)}")
    print("=" * 70)

trades = run()
report(trades)
