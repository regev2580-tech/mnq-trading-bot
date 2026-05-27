# Trading Bot — Claude Code Project

פרויקט ניתוח ומסחר אוטומטי ב-NQ/MNQ1! עם NinjaTrader 8 + TradingView + Claude AI.

## ארכיטקטורה

```
TradingView (MTF Analysis)
        ↓ bias + levels
orderflow.json ← NT8 ClaudeOrderFlow (כל טיק)
        ↓ score ≥ 3 + HTF confirmed
trade_signal.json ← Claude כותב
        ↓ NT8 ClaudeStrategy קורא (TTL 30 שניות)
position.json ← NT8 ClaudeStrategy כותב
```

## סקילים — פקודות זמינות

| פקודה | תיאור |
|-------|--------|
| `/tv-analysis` | ניתוח MTF מלא: Daily→1H→15M→5M + Pine levels + Kill Zone scenarios |
| `/nt-orderflow` | קריאת NT8, חישוב Valtos score, שליחת סיגנל לClaudeStrategy |

## קבצי הפרויקט העיקריים

### NinjaTrader MCP
```
ninjatrader-mcp/
├── auto_trader.js              # autonomous bot — node auto_trader.js --test
├── data/
│   ├── orderflow.json          # NT8 → Claude (live, כל טיק)
│   ├── position.json           # NT8 → Claude (מצב פוזיציה)
│   ├── trade_signal.json       # Claude → NT8 (סיגנל לביצוע)
│   ├── auto_log.txt            # לוג bot
│   └── auto_state.json         # מספר עסקאות + last signal time
```

### TradingView MCP
```
mcp-servers/tradingview-mcp/    # MCP server — CDP port 9222
```

### NT8 Indicators/Strategies
```
Documents/NinjaTrader 8/bin/Custom/
├── Indicators/ClaudeOrderFlow.cs   # כותב orderflow.json
└── Strategies/ClaudeStrategy.cs    # קורא trade_signal.json, כותב position.json
```

### Dashboard
```
dashboard/dashboard.html            # trading journal PRO (local)
C:\Users\DELL\Desktop\trading_journal_PRO.html
```

## שיטת המסחר — ICT 2022 + Valtos Order Flow

### Kill Zone
- **ישראל:** 16:30–18:00 (UTC+3 קיץ)
- **UTC:** 13:30–15:00
- סשן NY AM — הכי חשוב

### MTF Workflow (חובה לפני כל עסקה)
```
Daily  → bias (bull/bear), PDH/PDL
 ↓
1H     → structure, trend direction, order blocks
 ↓
15M    → Kill Zone setup, FVG, momentum
 ↓
5M     → entry execution (orderflow confirmation)
```
**אסור לקפוץ ישר ל-5M** ללא HTF analysis.

### Valtos Order Flow Score
| Signal | Points |
|--------|--------|
| CVD > 500 | +1 BULL |
| current_delta > 0 | +1 BULL |
| Stacked ASK imb (≥3 בבר) | +1 BULL per bar |
| Delta divergence bullish | +1 BULL |
| Trapped sellers | +1 BULL |
| CVD < -500 | +1 BEAR |
| current_delta < 0 | +1 BEAR |
| Stacked BID imb (≥3 בבר) | +1 BEAR per bar |
| Delta divergence bearish | +1 BEAR |
| Trapped buyers | +1 BEAR |

**Signal fires:** netScore ≥ +3 (LONG) או ≤ -3 (SHORT) + HTF confirms + R/R ≥ 2

## חוקי ברזל (נלמדו מהפסדים)

1. **SL מינימום 15 pts** — NQ עושה sweeps של 20-30 pts
2. **HTF חייב לאשר** — orderflow ללא context = 3 הפסדים (2026-05-27)
3. **Timestamp = Get-Date** — לא replay time (NT8 TTL 30 שניות)
4. **לחכות לסגירת נר** — לא להיכנס תוך כדי בר
5. **לא לסחור נגד daily trend** — ללא reversal signal ברור
6. **BE ב-1R** — להזיז SL לכניסה אחרי +1R

## הפעלה מלאה

### NT8 Live/Replay
```
1. NinjaTrader 8 → גרף NQ/MNQ 5M Volumetric
2. ClaudeOrderFlow indicator → מוסיף על הגרף
3. ClaudeStrategy → Sim101 (paper) או Playback101 (replay)
4. node ninjatrader-mcp/auto_trader.js --test   (--test = מעקף Kill Zone)
```

### TradingView
```
1. TradingView Desktop פתוח (CDP port 9222)
2. גרף: CME_MINI:MNQ1! | 5M
3. Indicators: Sav FX PDA, ICT 5M Stress Test, PSP, SMT/PSP/PCP MTF
4. /tv-analysis → ניתוח מלא
```

### Workflow משולב (מחר)
```
/tv-analysis          → HTF bias + key levels
/nt-orderflow         → confirm with orderflow → signal
```

## Dashboard
- `dashboard/dashboard.html` — local trading journal
- חשבון EVAL1 (ישן): 6 עסקאות (1W/1BE/4L)
- חשבון LUCID2: פעיל, נרשמות עסקאות חדשות
