# /nt-orderflow — NinjaTrader OrderFlow Scan + Signal

קורא נתוני NT8 בזמן אמת, מזהה Valtos Order Flow setups, שולח סיגנל ל-ClaudeStrategy.

## קבצים

| קובץ | תוכן | כותב |
|------|------|-------|
| `C:\Users\DELL\New folder\ninjatrader-mcp\data\orderflow.json` | bars, delta, CVD, imbalances | NT8 ClaudeOrderFlow indicator |
| `C:\Users\DELL\New folder\ninjatrader-mcp\data\position.json` | status, entry, uPnL, SL/TP | NT8 ClaudeStrategy |
| `C:\Users\DELL\New folder\ninjatrader-mcp\data\trade_signal.json` | סיגנל ממתין לביצוע | Claude (אני כותב) → NT8 קורא |

## רצף הפעולות

### שלב 1: קרא הכל (בו-זמנית)
```
Read orderflow.json
Read position.json  
Read trade_signal.json
```

### שלב 2: בדיקות מקדמיות
- **Data stale** (timestamp > 60 שניות): "NT8 לא פעיל — הפעל Market Replay או Live data"
- **Position open**: דווח `direction, entry, uPnL, current price` → אל תשלח סיגנל חדש
- **Signal pending**: "ממתין ל-NT8 לבצע סיגנל ב-[price]" → אל תשלח סיגנל חדש

### שלב 3: חשב Score (Valtos Method)

**BULL points (+1 כל אחד):**
```
CVD > 500                    → bull +1
current_delta > 0            → bull +1
כל bar עם ≥3 ASK imbalances  → bull +1 (per bar)
Delta divergence bullish:    → bull +1
  curr.low ≤ prev.low AND curr.delta > 0 AND curr.close > curr.open
Trapped sellers:             → bull +1
  BID imb ≤ bar.low + range×0.25 AND bar.close > bar.open
```

**BEAR points (+1 כל אחד):**
```
CVD < -500                   → bear +1
current_delta < 0            → bear +1
כל bar עם ≥3 BID imbalances  → bear +1 (per bar)
Delta divergence bearish:    → bear +1
  curr.high ≥ prev.high AND curr.delta < 0 AND curr.close < curr.open
Trapped buyers:              → bear +1
  ASK imb ≥ bar.high - range×0.25 AND bar.close < bar.open
```

```
netScore = bullScore - bearScore
bias = netScore ≥ 3 → LONG
       netScore ≤ -3 → SHORT
       else → NEUTRAL (no signal)
```

### שלב 4: HTF Gate — חובה! (לקח מ-2026-05-27)
לפני שליחת סיגנל, בדוק bias של TradingView:
- LONG מותר רק אם Daily + 1H trend = BULLISH
- SHORT מותר רק אם Daily + 1H trend = BEARISH
- אם TradingView סותר את orderflow → SKIP ("HTF conflict — no signal")
- אם TradingView לא זמין → המשך עם אזהרה

### שלב 5: חשב כניסה

**LONG:**
```javascript
entry = current price
allBidBelow = כל BID imb מכל הברים שמתחת למחיר
slBase = min(allBidBelow) אם קיים, אחרת min(last 3 bars low)
sl = round((slBase - 0.5) × 4) / 4
// מינימום SL: 15 pts מתחת לכניסה על NQ/MNQ
if (entry - sl < 15) sl = entry - 15
riskPts = entry - sl
minTarget = entry + riskPts × 2
targets = [cdh, pdh].filter(t => t >= minTarget)
tp = min(targets) אם קיים, אחרת entry + riskPts × 2
rr = (tp - entry) / riskPts
```

**SHORT:**
```javascript
entry = current price
allAskAbove = כל ASK imb מכל הברים שמעל למחיר
slBase = max(allAskAbove) אם קיים, אחרת max(last 3 bars high)
sl = round((slBase + 0.5) × 4) / 4
// מינימום SL: 15 pts מעל הכניסה
if (sl - entry < 15) sl = entry + 15
riskPts = sl - entry
minTarget = entry - riskPts × 2
targets = [cdl, pdl].filter(t => t <= minTarget)
tp = max(targets) אם קיים, אחרת entry - riskPts × 2
rr = (entry - tp) / riskPts
```

### שלב 6: שלח סיגנל (אם R/R ≥ 2.0)
```powershell
$ts = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")   # ⚠️ זמן אמת! לא replay time
$json = "{`"status`":`"pending`",`"action`":`"BUY/SELL`",`"price`":X,`"sl`":X,`"tp`":X,`"qty`":1,`"reason`":`"top 3 reasons`",`"timestamp`":`"$ts`"}"
[System.IO.File]::WriteAllText("C:\Users\DELL\New folder\ninjatrader-mcp\data\trade_signal.json", $json, [System.Text.UTF8Encoding]::new($false))
```

## חוקי ברזל

| חוק | הסיבה |
|-----|--------|
| SL מינימום 15 pts | NQ עושה sweeps של 20-30 pts |
| Timestamp = Get-Date | NT8 בודק TTL 30 שניות — replay timestamp = פג מיד |
| HTF חייב לאשר | 3 הפסדים ב-2026-05-27 מ-orderflow ללא context |
| לא לשלוח אם position פתוח | ClaudeStrategy מתבלבל |
| לא לשלוח אם signal pending | Race condition |
| Kill Zone בלבד | 13:30-15:00 UTC = 16:30-18:00 Israel (ניתן לעקוף עם --test) |

## Capitulation Rule (Special Case)
אם בר קודם: volume > 2,000 AND delta < -140 (capitulation bar)
ובר נוכחי: delta > 0 (buyers absorbing)
→ שלח LONG signal גם אם score < 3 (bypass score filter)

## רצף הפעלה מלא (NT8 + Claude)
```
1. פתח NinjaTrader 8
2. טען גרף NQ 09-25 (או MNQ1!) עם 5M Volumetric
3. ClaudeOrderFlow indicator פעיל → כותב orderflow.json כל טיק
4. ClaudeStrategy פעיל על Sim101/Playback101 → קורא trade_signal.json, כותב position.json
5. הרץ: node "C:\Users\DELL\New folder\ninjatrader-mcp\auto_trader.js" --test
6. או: קרא /nt-orderflow ואני אנתח ואחליט ידנית
```
