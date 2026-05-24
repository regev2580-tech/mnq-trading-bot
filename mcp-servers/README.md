# MCP Servers — שרתי Model Context Protocol

שרתי MCP המאפשרים ל-Claude לראות ולשלוט בפלטפורמות המסחר.

## תת-תיקיות

| תיקייה | פלטפורמה | סטטוס |
|--------|---------|-------|
| [`tradingview-mcp/`](./tradingview-mcp/) | TradingView — קריאת גרפים וניתוח | ✅ פעיל |
| [`ninjatrader-mcp/`](./ninjatrader-mcp/) | NinjaTrader 8 — ביצוע פקודות | 🚧 בפיתוח |

## ארכיטקטורה

```
TradingView (גרף) → tradingview-mcp → Claude
                                           ↓
NinjaTrader (פקודות) ← ninjatrader-mcp ←──┘
```

## הגדרת MCP ב-Claude Code

קובץ תצורה: `C:\Users\DELL\.claude\mcp.json`

## הפעלה

```bash
# TradingView MCP
cd mcp-servers/tradingview-mcp
npm install
npm start

# NinjaTrader MCP
cd mcp-servers/ninjatrader-mcp
npm install
node src/server.js
```
