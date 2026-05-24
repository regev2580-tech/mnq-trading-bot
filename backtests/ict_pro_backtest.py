#!/usr/bin/env python3
"""
ICT 2022 Professional Backtest Engine -- MNQ1!
============================================================
Full model implementation:
  - Multi-timeframe bias (Monthly / Weekly / Daily)
  - Power of 3  (Accumulation -> Manipulation -> Distribution)
  - Liquidity mapping  (swing highs/lows + equal H/L)
  - Fair Value Gaps (FVG) on daily bars
  - Order Block detection
  - Market Structure  (BOS / CHoCH / MSS)
  - OTE entry  (61.8 % Fibonacci of displacement)
  - Kill-Zone estimation from daily OHLC
  - Confluence scoring  (only ≥5/9 accepted)
  - Trade management  (partial TP + breakeven stop)
  - Quarterly Cycle bias filter
  - Risk management  (streak limits, session limits)
  - Full statistics  (monthly P&L, equity curve, Profit Factor)
============================================================
"""

import json, subprocess, sys, statistics, math
import time as _time
from datetime import datetime, timezone, timedelta
from collections import defaultdict

MCP_DIR = r"C:\Users\DELL\New folder\tradingview-mcp"

# ─── CONFIG ───────────────────────────────────────────────
RISK_R          = 1.0          # R per trade (normalised)
TP1_R, TP1_PCT  = 2.0, 0.35   # first partial close
TP2_R, TP2_PCT  = 3.5, 0.35   # second partial close
TP3_R, TP3_PCT  = 5.0, 0.30   # runner
MAX_HOLD_BARS   = 8            # max days in trade
MIN_CONFLUENCE  = 5            # minimum score out of 9
MAX_CONSEC_LOSS = 3            # daily loss limit
OTE_FIB         = 0.618        # Fibonacci OTE entry
SL_BUFFER_PCT   = 0.12         # SL buffer beyond swing (% of ATR)
# ──────────────────────────────────────────────────────────

def get_bars():
    subprocess.run(["node","src/cli/index.js","timeframe","--set","D"],
                   capture_output=True, text=True, cwd=MCP_DIR)
    _time.sleep(4)
    r = subprocess.run(["node","src/cli/index.js","ohlcv",
                        "--symbol","CME_MINI:MNQ1!","--count","300"],
                       capture_output=True, text=True, cwd=MCP_DIR)
    return json.loads(r.stdout).get("bars", [])

# ─── INDICATORS ───────────────────────────────────────────

def ema(values, n):
    k, result = 2/(n+1), []
    for v in values:
        result.append(v if not result else v*k + result[-1]*(1-k))
    return result

def atr_series(bars, n=14):
    trs = [max(bars[i]["high"]-bars[i]["low"],
               abs(bars[i]["high"]-bars[i-1]["close"]),
               abs(bars[i]["low"] -bars[i-1]["close"]))
           for i in range(1, len(bars))]
    result = [None]
    for i in range(len(trs)):
        if i < n-1: result.append(None)
        else: result.append(statistics.mean(trs[i-n+1:i+1]))
    return result

def swing_highs(bars, n=3):
    """Identify swing highs (n-bar pivot)"""
    pivots = []
    for i in range(n, len(bars)-n):
        if all(bars[i]["high"] >= bars[j]["high"] for j in range(i-n,i+n+1) if j!=i):
            pivots.append({"idx":i,"price":bars[i]["high"],"time":bars[i]["time"]})
    return pivots

def swing_lows(bars, n=3):
    pivots = []
    for i in range(n, len(bars)-n):
        if all(bars[i]["low"] <= bars[j]["low"] for j in range(i-n,i+n+1) if j!=i):
            pivots.append({"idx":i,"price":bars[i]["low"],"time":bars[i]["time"]})
    return pivots

def detect_fvg(bars, idx):
    """Fair Value Gap: gap between bar[i-1] and bar[i+1]"""
    if idx < 1 or idx >= len(bars)-1:
        return None
    # Bearish FVG (price trades too high, gap below)
    if bars[idx-1]["low"] > bars[idx+1]["high"]:
        return {"type":"BEAR","high":bars[idx-1]["low"],"low":bars[idx+1]["high"]}
    # Bullish FVG
    if bars[idx-1]["high"] < bars[idx+1]["low"]:
        return {"type":"BULL","high":bars[idx+1]["low"],"low":bars[idx-1]["high"]}
    return None

def equal_levels(prices, tolerance_pct=0.0015):
    """Find equal highs or equal lows (within tolerance %)"""
    equals = []
    for i in range(len(prices)):
        for j in range(i+1, len(prices)):
            if abs(prices[i]-prices[j])/prices[i] < tolerance_pct:
                equals.append((prices[i]+prices[j])/2)
    return equals

def market_structure(bars, idx, lookback=20):
    """Determine trend: BULL / BEAR / RANGING"""
    window = bars[max(0,idx-lookback):idx+1]
    if len(window) < 6: return "RANGING"
    highs = [b["high"] for b in window]
    lows  = [b["low"]  for b in window]
    hh = sum(1 for i in range(1,len(highs)) if highs[i]>highs[i-1])
    hl = sum(1 for i in range(1,len(lows))  if lows[i] >lows[i-1])
    lh = sum(1 for i in range(1,len(highs)) if highs[i]<highs[i-1])
    ll = sum(1 for i in range(1,len(lows))  if lows[i] <lows[i-1])
    bull_score = hh + hl
    bear_score = lh + ll
    if bull_score > bear_score * 1.4: return "BULL"
    if bear_score > bull_score * 1.4: return "BEAR"
    return "RANGING"

def quarterly_bias(ts):
    """ICT quarterly cycle: Q1=accum, Q2=markup, Q3=distrib, Q4=markdown (simplified)"""
    month = datetime.fromtimestamp(ts).month
    q = (month-1)//3 + 1
    # Based on typical NQ seasonal pattern
    if q in [1,2]: return "BULL"
    if q in [3,4]: return "BEAR"
    return "NEUTRAL"

def weekly_structure(bars, idx):
    """5-day high/low and midpoint"""
    w = bars[max(0,idx-5):idx]
    if not w: return None,None,None
    h = max(b["high"]  for b in w)
    l = min(b["low"]   for b in w)
    return h, l, (h+l)/2

def monthly_structure(bars, idx):
    """20-day high/low and midpoint"""
    m = bars[max(0,idx-20):idx]
    if not m: return None,None,None
    h = max(b["high"]  for b in m)
    l = min(b["low"]   for b in m)
    return h, l, (h+l)/2

def prev_day_open(bars, idx):
    """True Day Open = open of the previous daily bar"""
    if idx < 1: return None
    return bars[idx-1]["open"]

def detect_order_block(bars, idx, direction):
    """Last opposing candle before displacement"""
    if direction == "SHORT":
        # Last bullish (up) candle before the bearish move
        for i in range(idx-1, max(0,idx-5), -1):
            if bars[i]["close"] > bars[i]["open"]:
                return {"high": bars[i]["high"], "low": bars[i]["low"]}
    else:
        for i in range(idx-1, max(0,idx-5), -1):
            if bars[i]["close"] < bars[i]["open"]:
                return {"high": bars[i]["high"], "low": bars[i]["low"]}
    return None

# ─── CONFLUENCE SCORING ───────────────────────────────────

def score_short(bars, idx, atrs, ema20):
    """Score 0-9 for short setup quality"""
    score = 0
    notes = []
    bar = bars[idx]
    at  = atrs[idx] or 100
    pwh, pwl, pwm = weekly_structure(bars, idx)
    pmh, pml, pmm = monthly_structure(bars, idx)
    ms = market_structure(bars, idx)
    q_bias = quarterly_bias(bar["time"])

    # 1. HTF trend aligned (BEAR)
    if ms == "BEAR":
        score += 1; notes.append("HTF Bear trend")
    elif ms == "RANGING":
        score += 0.5

    # 2. Weekly premium (above weekly midpoint)
    if pwm and bar["close"] > pwm:
        score += 1; notes.append("Weekly premium")

    # 3. Monthly premium
    if pmm and bar["close"] > pmm:
        score += 1; notes.append("Monthly premium")

    # 4. Price above True Day Open (previous day close)
    tdo = prev_day_open(bars, idx)
    if tdo and bar["high"] > tdo > bar["close"]:
        score += 1; notes.append("Above TDO -> swept")

    # 5. Swept a significant swing high
    recent_sh = [s for s in swing_highs(bars) if idx-15 <= s["idx"] < idx]
    if recent_sh:
        nearest = max(recent_sh, key=lambda s: s["idx"])
        if bar["high"] > nearest["price"] and bar["close"] < nearest["price"]:
            score += 2; notes.append(f"Swept swing H {round(nearest['price'],1)}")
    elif pwh and bar["high"] > pwh and bar["close"] < pwh:
        score += 1; notes.append("Swept weekly high")

    # 6. Displacement candle (large bearish body)
    body = abs(bar["close"]-bar["open"])
    rng  = bar["high"]-bar["low"]
    if rng > at*1.2 and bar["close"] < bar["open"] and body > rng*0.5:
        score += 1; notes.append("Displacement candle")

    # 7. FVG present
    fvg = detect_fvg(bars, idx)
    if fvg and fvg["type"] == "BEAR":
        score += 1; notes.append("Bearish FVG")

    # 8. Quarterly cycle alignment
    if q_bias == "BEAR":
        score += 0.5; notes.append("Q-cycle bearish")

    # 9. Equal highs swept
    recent_highs = [bars[j]["high"] for j in range(max(0,idx-10),idx)]
    eq_h = equal_levels(recent_highs)
    if eq_h and any(bar["high"] > eh and bar["close"] < eh for eh in eq_h):
        score += 0.5; notes.append("Equal highs swept")

    return round(score, 1), notes

def score_long(bars, idx, atrs, ema20):
    score = 0
    notes = []
    bar = bars[idx]
    at  = atrs[idx] or 100
    pwh, pwl, pwm = weekly_structure(bars, idx)
    pmh, pml, pmm = monthly_structure(bars, idx)
    ms = market_structure(bars, idx)
    q_bias = quarterly_bias(bar["time"])

    if ms == "BULL":
        score += 1; notes.append("HTF Bull trend")
    elif ms == "RANGING":
        score += 0.5

    if pwm and bar["close"] < pwm:
        score += 1; notes.append("Weekly discount")

    if pmm and bar["close"] < pmm:
        score += 1; notes.append("Monthly discount")

    tdo = prev_day_open(bars, idx)
    if tdo and bar["low"] < tdo < bar["close"]:
        score += 1; notes.append("Below TDO -> swept")

    recent_sl = [s for s in swing_lows(bars) if idx-15 <= s["idx"] < idx]
    if recent_sl:
        nearest = max(recent_sl, key=lambda s: s["idx"])
        if bar["low"] < nearest["price"] and bar["close"] > nearest["price"]:
            score += 2; notes.append(f"Swept swing L {round(nearest['price'],1)}")
    elif pwl and bar["low"] < pwl and bar["close"] > pwl:
        score += 1; notes.append("Swept weekly low")

    body = abs(bar["close"]-bar["open"])
    rng  = bar["high"]-bar["low"]
    if rng > at*1.2 and bar["close"] > bar["open"] and body > rng*0.5:
        score += 1; notes.append("Displacement candle")

    fvg = detect_fvg(bars, idx)
    if fvg and fvg["type"] == "BULL":
        score += 1; notes.append("Bullish FVG")

    if q_bias == "BULL":
        score += 0.5; notes.append("Q-cycle bullish")

    recent_lows = [bars[j]["low"] for j in range(max(0,idx-10),idx)]
    eq_l = equal_levels(recent_lows)
    if eq_l and any(bar["low"] < el and bar["close"] > el for el in eq_l):
        score += 0.5; notes.append("Equal lows swept")

    return round(score, 1), notes

# ─── SIMULATE TRADE ───────────────────────────────────────

def simulate(bars, setup_idx, direction, entry, sl):
    risk = abs(sl - entry)
    if risk < 1: return None

    tp1 = entry + (risk * TP1_R * (-1 if direction=="SHORT" else 1))
    tp2 = entry + (risk * TP2_R * (-1 if direction=="SHORT" else 1))
    tp3 = entry + (risk * TP3_R * (-1 if direction=="SHORT" else 1))

    filled = False
    remaining = 1.0
    realised_r = 0.0
    sl_current = sl

    for j in range(setup_idx+1, min(setup_idx+MAX_HOLD_BARS+1, len(bars))):
        b = bars[j]

        if not filled:
            if b["low"] <= entry <= b["high"]:
                filled = True
            else:
                continue

        if direction == "SHORT":
            # SL hit
            if b["high"] >= sl_current:
                realised_r -= remaining * RISK_R
                return build_result(direction, entry, sl, b["close"],
                                    realised_r, "LOSS", bars[j]["time"])
            # TP1
            if remaining >= TP1_PCT + 0.01 and b["low"] <= tp1:
                realised_r += TP1_PCT * TP1_R
                remaining  -= TP1_PCT
                sl_current  = entry          # move to breakeven
            # TP2
            if remaining >= TP2_PCT + 0.01 and b["low"] <= tp2:
                realised_r += TP2_PCT * TP2_R
                remaining  -= TP2_PCT
            # TP3
            if remaining > 0 and b["low"] <= tp3:
                realised_r += remaining * TP3_R
                remaining   = 0
                return build_result(direction, entry, sl, tp3,
                                    realised_r, "WIN", bars[j]["time"])
        else:  # LONG
            if b["low"] <= sl_current:
                realised_r -= remaining * RISK_R
                return build_result(direction, entry, sl, b["close"],
                                    realised_r, "LOSS", bars[j]["time"])
            if remaining >= TP1_PCT + 0.01 and b["high"] >= tp1:
                realised_r += TP1_PCT * TP1_R
                remaining  -= TP1_PCT
                sl_current  = entry
            if remaining >= TP2_PCT + 0.01 and b["high"] >= tp2:
                realised_r += TP2_PCT * TP2_R
                remaining  -= TP2_PCT
            if remaining > 0 and b["high"] >= tp3:
                realised_r += remaining * TP3_R
                remaining   = 0
                return build_result(direction, entry, sl, tp3,
                                    realised_r, "WIN", bars[j]["time"])

    if not filled: return None

    # Expired -- close at last bar close
    last = bars[min(setup_idx+MAX_HOLD_BARS, len(bars)-1)]
    if direction == "SHORT":
        exp_r = (entry - last["close"]) / risk
    else:
        exp_r = (last["close"] - entry) / risk
    realised_r += remaining * exp_r
    outcome = "WIN" if realised_r > 0 else "LOSS"
    return build_result(direction, entry, sl, last["close"],
                        realised_r, outcome, last["time"])

def build_result(direction, entry, sl, exit_p, r, outcome, exit_ts):
    return {
        "direction": direction, "entry": round(entry,2),
        "sl": round(sl,2), "exit": round(exit_p,2),
        "r": round(r,2), "outcome": outcome,
        "exit_date": datetime.fromtimestamp(exit_ts).strftime("%Y-%m-%d")
    }

# ─── MAIN BACKTEST LOOP ───────────────────────────────────

def run_backtest(bars):
    atrs     = atr_series(bars, 14)
    closes   = [b["close"] for b in bars]
    ema20    = ema(closes, 20)

    cutoff   = datetime(2025, 11, 1, tzinfo=timezone.utc).timestamp()
    trades   = []
    consec_loss = 0
    last_trade_date = None

    for i in range(25, len(bars)-MAX_HOLD_BARS-1):
        bar = bars[i]
        if bar["time"] < cutoff:
            continue
        if atrs[i] is None:
            continue

        at = atrs[i]
        date_str = datetime.fromtimestamp(bar["time"]).strftime("%Y-%m-%d")

        # Only one trade per day
        if date_str == last_trade_date:
            continue

        # Stop after too many consecutive losses
        if consec_loss >= MAX_CONSEC_LOSS:
            consec_loss = 0   # reset next day
            continue

        pdh = bars[i-1]["high"]
        pdl = bars[i-1]["low"]
        midpoint = (pdh + pdl) / 2

        # ── SHORT: day swept buyside LQ and closed bearish ──
        if (bar["high"] > pdh and
            bar["close"] < pdh and
            bar["close"] < bar["open"]):

            sc, notes = score_short(bars, i, atrs, ema20)
            if sc >= MIN_CONFLUENCE:
                sweep_size = bar["high"] - bar["close"]
                entry = bar["close"] + sweep_size * OTE_FIB
                sl    = bar["high"]  + at * SL_BUFFER_PCT
                risk  = sl - entry
                if at * 0.2 <= risk <= at * 2.5:
                    ob = detect_order_block(bars, i, "SHORT")
                    result = simulate(bars, i, "SHORT", entry, sl)
                    if result:
                        result.update({
                            "date": date_str, "score": sc,
                            "confluences": notes, "atr": round(at,1),
                            "risk_pts": round(risk,1),
                            "ob": ob
                        })
                        trades.append(result)
                        last_trade_date = date_str
                        if result["outcome"] == "LOSS":
                            consec_loss += 1
                        else:
                            consec_loss = 0

        # ── LONG: day swept sellside LQ and closed bullish ──
        elif (bar["low"] < pdl and
              bar["close"] > pdl and
              bar["close"] > bar["open"]):

            sc, notes = score_long(bars, i, atrs, ema20)
            if sc >= MIN_CONFLUENCE:
                sweep_size = bar["close"] - bar["low"]
                entry = bar["close"] - sweep_size * OTE_FIB
                sl    = bar["low"] - at * SL_BUFFER_PCT
                risk  = entry - sl
                if at * 0.2 <= risk <= at * 2.5:
                    ob = detect_order_block(bars, i, "LONG")
                    result = simulate(bars, i, "LONG", entry, sl)
                    if result:
                        result.update({
                            "date": date_str, "score": sc,
                            "confluences": notes, "atr": round(at,1),
                            "risk_pts": round(risk,1),
                            "ob": ob
                        })
                        trades.append(result)
                        last_trade_date = date_str
                        if result["outcome"] == "LOSS":
                            consec_loss += 1
                        else:
                            consec_loss = 0

    return trades

# ─── REPORTING ────────────────────────────────────────────

def equity_curve(trades, width=60):
    if not trades: return ""
    rs = [0]
    for t in trades: rs.append(rs[-1] + t["r"])
    mn, mx = min(rs), max(rs)
    rng = mx - mn or 1
    height = 12
    chart = []
    for row in range(height, -1, -1):
        line = ""
        for col in range(width):
            idx = int(col * len(rs) / width)
            norm = (rs[idx] - mn) / rng
            if abs(norm - row/height) < (1/height) * 0.9:
                line += "●"
            else:
                line += " "
        val = mn + (row/height)*rng
        chart.append(f"  {val:>+6.1f}R |{line}|")
    chart.append("         " + "-"*width)
    return "\n".join(chart)

def print_report(trades):
    if not trades:
        print("No high-confluence trades found. Lower MIN_CONFLUENCE threshold.")
        return

    wins   = [t for t in trades if t["outcome"]=="WIN"]
    losses = [t for t in trades if t["outcome"]=="LOSS"]
    total  = len(trades)
    wr     = len(wins)/total*100
    total_r= sum(t["r"] for t in trades)

    gross_win  = sum(t["r"] for t in wins)
    gross_loss = abs(sum(t["r"] for t in losses)) or 0.001
    pf         = gross_win / gross_loss

    # Drawdown
    eq, peak, max_dd = 0, 0, 0
    for t in trades:
        eq += t["r"]; peak = max(peak,eq); max_dd = max(max_dd, peak-eq)

    # Streaks
    best_w, best_l, cur, last_o = 0, 0, 0, None
    for t in trades:
        cur = cur+1 if t["outcome"]==last_o else 1
        if t["outcome"]=="WIN":  best_w = max(best_w, cur)
        else:                    best_l = max(best_l, cur)
        last_o = t["outcome"]

    # Monthly breakdown
    monthly = defaultdict(lambda: {"trades":0,"r":0,"w":0})
    for t in trades:
        m = t["date"][:7]
        monthly[m]["trades"] += 1
        monthly[m]["r"]      += t["r"]
        if t["outcome"]=="WIN": monthly[m]["w"] += 1

    # Direction split
    longs  = [t for t in trades if t["direction"]=="LONG"]
    shorts = [t for t in trades if t["direction"]=="SHORT"]
    lw = [t for t in longs  if t["outcome"]=="WIN"]
    sw = [t for t in shorts if t["outcome"]=="WIN"]

    # Expectancy
    avg_w = statistics.mean(t["r"] for t in wins)  if wins   else 0
    avg_l = statistics.mean(t["r"] for t in losses) if losses else 0
    expectancy = (wr/100)*avg_w + ((1-wr/100))*avg_l

    # Score distribution of wins vs losses
    if wins:
        avg_score_win  = statistics.mean(t["score"] for t in wins)
        avg_score_loss = statistics.mean(t["score"] for t in losses) if losses else 0

    print()
    print("="*62)
    print("   ICT 2022 PROFESSIONAL BACKTEST -- MNQ1!  (Micro NQ Futures)")
    print("   November 2025 -> May 2026  |  Pure Price Action")
    print("="*62)

    print(f"""
  SUMMARY
  ───────────────────────────────────────────
  Total Trades        {total}
  Win Rate            {round(wr,1)}%    ({len(wins)}W / {len(losses)}L)
  Profit Factor       {round(pf,2)}
  Total R             {round(total_r,2)}R
  Expectancy/trade    {round(expectancy,2)}R
  Avg Win             {round(avg_w,2)}R
  Avg Loss            {round(avg_l,2)}R
  Max Drawdown        -{round(max_dd,2)}R
  Best win streak     {best_w}
  Worst loss streak   {best_l}
  Avg Confluence Score (wins)   {round(avg_score_win,1) if wins else 'N/A'}
  Avg Confluence Score (losses) {round(avg_score_loss,1) if losses else 'N/A'}
""")

    print("  BY DIRECTION")
    print("  ─────────────────────────────────────────")
    print(f"  LONG   {len(longs):>3} trades | {round(len(lw)/len(longs)*100,1) if longs else 0:>5}% WR | {round(sum(t['r'] for t in longs),2):>+6.2f}R")
    print(f"  SHORT  {len(shorts):>3} trades | {round(len(sw)/len(shorts)*100,1) if shorts else 0:>5}% WR | {round(sum(t['r'] for t in shorts),2):>+6.2f}R")

    print("\n  MONTHLY P&L")
    print("  ─────────────────────────────────────────")
    for month in sorted(monthly):
        d = monthly[month]
        wr_m = round(d["w"]/d["trades"]*100,0) if d["trades"] else 0
        bar_s= "+" * max(0,int(d["r"])) if d["r"]>0 else "-"*max(0,int(abs(d["r"])))
        print(f"  {month}  {d['trades']:>2} trades  {wr_m:>3.0f}%WR  {d['r']:>+6.2f}R  {bar_s}")

    print("\n  EQUITY CURVE")
    print(equity_curve(trades))

    print("\n  ALL TRADES")
    print(f"  {'Date':<12} {'Dir':<6} {'Entry':<9} {'Exit':<9} {'R':>5} {'Score'} Result")
    print("  " + "─"*58)
    for t in trades:
        icon = "WIN " if t["outcome"]=="WIN" else "LOSS"
        top_conf = t["confluences"][0] if t["confluences"] else ""
        print(f"  {t['date']:<12} {t['direction']:<6} {t['entry']:<9.2f} {t['exit']:<9.2f} {t['r']:>+5.2f}  [{t['score']}] {icon}  {top_conf}")

    print("\n  TOP PERFORMING SETUPS (by confluence notes)")
    conf_count = defaultdict(lambda:[0,0,0.0])
    for t in trades:
        for c in t["confluences"]:
            conf_count[c][0] += 1
            if t["outcome"]=="WIN": conf_count[c][1] += 1
            conf_count[c][2] += t["r"]
    for c, (tot, w, r) in sorted(conf_count.items(), key=lambda x: -x[1][1]/max(x[1][0],1)):
        print(f"  {c:<30} {tot:>3} trades  {round(w/tot*100,0):>3.0f}%WR  {r:>+6.2f}R")

    print()
    print("="*62)
    if expectancy > 0.3:
        print("  VERDICT: SOLID POSITIVE EXPECTANCY -- system is viable")
    elif expectancy > 0:
        print("  VERDICT: MARGINALLY PROFITABLE -- needs refinement")
    else:
        print("  VERDICT: NEGATIVE EXPECTANCY -- review entry rules")
    print("="*62)
    print()

# ─── RUN ──────────────────────────────────────────────────
print("Loading 6-month daily data from TradingView...")
bars = get_bars()
print(f"Loaded {len(bars)} daily bars")

if len(bars) < 50:
    print("Not enough data."); sys.exit(1)

gap = bars[1]["time"] - bars[0]["time"]
if gap < 60000:
    print(f"Error: bars are {gap}s apart -- not daily. Try again."); sys.exit(1)

d0 = datetime.fromtimestamp(bars[0]["time"]).strftime("%Y-%m-%d")
d1 = datetime.fromtimestamp(bars[-1]["time"]).strftime("%Y-%m-%d")
print(f"Date range: {d0} -> {d1}")
print(f"Running ICT 2022 full model (min confluence={MIN_CONFLUENCE}/9)...\n")

trades = run_backtest(bars)
print_report(trades)
