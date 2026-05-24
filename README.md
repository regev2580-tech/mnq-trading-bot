# 🤖 Trading Bot — MNQ1! (Micro E-mini Nasdaq)

מערכת מסחר אוטומטית מבוססת ICT 2022 לנכס MNQ1! עבור חשבון Prop Eval של Lucid Trader.

## מבנה הפרויקט

| תיקייה | תוכן |
|--------|-------|
| [`dashboard/`](./dashboard/) | דשבורד ניטור עסקאות (HTML + Python) |
| [`backtests/`](./backtests/) | בדיקות היסטוריות לאסטרטגיות ICT |
| [`mcp-servers/`](./mcp-servers/) | שרתי MCP — TradingView ו-NinjaTrader |
| [`monitoring/`](./monitoring/) | ניטור NY Kill Zone בזמן אמת |
| [`scripts/`](./scripts/) | סקריפטי הפעלה ועזר |
| [`trade-journal/`](./trade-journal/) | יומן עסקאות ונתוני ביצועים |
| [`docs/`](./docs/) | תיעוד, סיכומים ולוגים |

## החשבון

- **ברוקר:** Tradovate
- **חברת Prop:** Lucid Trader (אישרו אוטומציה)
- **נכס:** MNQ1! — Micro E-mini Nasdaq-100
- **ערך נקודה:** $0.50

## האסטרטגיה

ICT 2022 — Order Blocks, FVG, Liquidity Sweeps, Kill Zones  
NY AM Kill Zone: 09:30–11:00 EST

## מצב נוכחי

- ✅ TradingView MCP Server מותקן
- ✅ NinjaTrader MCP Server בפיתוח
- ⏳ Claude API Key — נדרש
- ⏳ TradingView Webhook — נדרש (Plus plan)

## הפעלה מהירה

```bat
scripts\launch_tradingview_debug.bat
```

---
**שפה:** Python 3.14 | Node.js v24 | NinjaTrader 8
