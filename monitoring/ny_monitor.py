#!/usr/bin/env python3
"""
NY AM Kill Zone Monitor — MNQ1!
Monitors price at 16:30 Israel time (13:30 UTC) and identifies first setup
"""
import json, subprocess, time, sys
from datetime import datetime, timezone, timedelta

MCP_DIR = r"C:\Users\DELL\New folder\tradingview-mcp"

def get_quote():
    r = subprocess.run(
        ["node","src/cli/index.js","quote","--symbol","CME_MINI:MNQ1!"],
        capture_output=True, text=True, cwd=MCP_DIR
    )
    return json.loads(r.stdout)

def get_bars(count=30):
    r = subprocess.run(
        ["node","src/cli/index.js","ohlcv","--symbol","CME_MINI:MNQ1!","--count",str(count)],
        capture_output=True, text=True, cwd=MCP_DIR
    )
    return json.loads(r.stdout).get("bars", [])

def get_labels():
    r = subprocess.run(
        ["node","src/cli/index.js","data","labels"],
        capture_output=True, text=True, cwd=MCP_DIR
    )
    try:
        return json.loads(r.stdout)
    except:
        return {}

def get_levels(labels_data):
    levels = {}
    for study in labels_data.get("studies", []):
        for lbl in study.get("labels", []):
            t = lbl.get("text","")
            p = lbl.get("price")
            if p and t:
                levels[t] = p
    return levels

def ny_open_status():
    now_utc = datetime.now(timezone.utc)
    now_il  = now_utc + timedelta(hours=3)
    h, m = now_il.hour, now_il.minute

    # NY AM: 16:30 - 19:00 Israel time
    in_ny = (h == 16 and m >= 30) or (17 <= h < 19)
    mins_to_ny = max(0, (16*60+30) - (h*60+m)) if h < 16 or (h==16 and m<30) else 0

    return in_ny, mins_to_ny, now_il.strftime("%H:%M:%S")

def atr(bars, n=14):
    import statistics
    trs = [max(bars[i]["high"]-bars[i]["low"],
               abs(bars[i]["high"]-bars[i-1]["close"]),
               abs(bars[i]["low"]-bars[i-1]["close"]))
           for i in range(1,len(bars))]
    return statistics.mean(trs[-n:]) if len(trs) >= n else (statistics.mean(trs) if trs else 30)

def analyze_setup(bars, levels):
    if len(bars) < 20:
        return None

    avg_atr = atr(bars)
    bar = bars[-1]
    prev_bars = bars[-20:-1]
    pdh = max(b["high"] for b in prev_bars)
    pdl = min(b["low"]  for b in prev_bars)
    midpoint = (pdh + pdl) / 2

    setup = None

    # SHORT: swept high
    if bar["high"] > pdh and bar["close"] < pdh and bar["close"] < bar["open"]:
        sweep_range = bar["high"] - bar["close"]
        entry = bar["close"] + sweep_range * 0.618
        sl    = bar["high"] + avg_atr * 0.15
        risk  = sl - entry
        if avg_atr * 0.15 < risk < avg_atr * 2:
            setup = {
                "dir": "SHORT",
                "entry": round(entry,2),
                "sl":    round(sl,2),
                "tp1":   round(entry - risk*2, 2),
                "tp2":   round(entry - risk*3, 2),
                "tp3":   round(entry - risk*4, 2),
                "risk":  round(risk,1),
                "swept": round(pdh,2),
                "reason": f"Swept session high {round(pdh,2)}"
            }

    # LONG: swept low
    if not setup and bar["low"] < pdl and bar["close"] > pdl and bar["close"] > bar["open"]:
        sweep_range = bar["close"] - bar["low"]
        entry = bar["close"] - sweep_range * 0.618
        sl    = bar["low"] - avg_atr * 0.15
        risk  = entry - sl
        if avg_atr * 0.15 < risk < avg_atr * 2:
            setup = {
                "dir": "LONG",
                "entry": round(entry,2),
                "sl":    round(sl,2),
                "tp1":   round(entry + risk*2, 2),
                "tp2":   round(entry + risk*3, 2),
                "tp3":   round(entry + risk*4, 2),
                "risk":  round(risk,1),
                "swept": round(pdl,2),
                "reason": f"Swept session low {round(pdl,2)}"
            }

    return setup

print("\n" + "="*55)
print("   NY AM KILL ZONE MONITOR — MNQ1!")
print("   Kill Zone: 16:30-19:00 Israel time")
print("="*55)

check_count = 0
while True:
    in_ny, mins_to, time_il = ny_open_status()

    if not in_ny:
        if check_count % 6 == 0:  # Print every 60 seconds
            print(f"\r  [{time_il}] Waiting for NY AM... ({mins_to} min)    ", end="", flush=True)
        check_count += 1
        time.sleep(10)
        continue

    # We're in NY Kill Zone
    print(f"\n\n  [{time_il}] *** NY AM KILL ZONE OPEN ***")

    quote = get_quote()
    bars  = get_bars(30)
    labels = get_labels()
    levels = get_levels(labels)
    price = quote.get("close", 0)

    print(f"\n  Current Price: {price}")
    print(f"  Key Levels:")
    for name, lvl in levels.items():
        if lvl and isinstance(lvl, (int,float)):
            dist = price - lvl
            print(f"    {name:<22}: {lvl:<10} ({'+' if dist>0 else ''}{round(dist,1)} from price)")

    setup = analyze_setup(bars, levels)
    if setup:
        print(f"\n  *** SETUP FOUND ***")
        print(f"  Direction: {setup['dir']}")
        print(f"  Entry:     {setup['entry']}")
        print(f"  SL:        {setup['sl']}  (risk: {setup['risk']} pts)")
        print(f"  TP1:       {setup['tp1']}  (2R = {setup['risk']*2} pts)")
        print(f"  TP2:       {setup['tp2']}  (3R = {setup['risk']*3} pts)")
        print(f"  TP3:       {setup['tp3']}  (4R = {setup['risk']*4} pts)")
        print(f"  Reason:    {setup['reason']}")
        print(f"\n  Screenshot saved — check Claude for visual confirmation")
        # Take screenshot
        subprocess.run(["node","src/cli/index.js","screenshot"],
                      capture_output=True, text=True, cwd=MCP_DIR)
    else:
        print(f"  No clean setup yet — monitoring...")

    print(f"\n  Next check in 60 seconds...")
    time.sleep(60)
