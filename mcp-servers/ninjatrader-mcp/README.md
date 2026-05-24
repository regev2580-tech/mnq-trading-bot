# NinjaTrader MCP Server

שרת MCP לחיבור Claude עם NinjaTrader 8 לביצוע פקודות מסחר.

## סטטוס: 🚧 בפיתוח

## קבצים

| קובץ | תיאור |
|------|-------|
| `src/server.js` | שרת MCP ראשי |
| `src/cli/` | כלי CLI לבדיקה |
| `data/` | נתוני Order Flow |
| `ClaudeOrderFlow.cs` | אינדיקטור NinjaTrader שמייצא נתונים |
| `package.json` | הגדרות Node.js |

## ארכיטקטורה

```
NinjaTrader 8
    ↓ (ClaudeOrderFlow.cs — כותב קובץ JSON)
C:\NinjaTrader8\OrderFlowData\
    ↓ (server.js קורא בזמן אמת)
MCP Server (localhost:3001)
    ↓
Claude Code
```

## התקנה

```bash
npm install
```

## הפעלה

```bash
node src/server.js
```

## כלים זמינים ל-Claude

- `get_order_flow` — Order Flow נוכחי
- `get_market_depth` — עומק שוק
- `place_order` — ביצוע פקודה
- `get_positions` — פוזיציות פתוחות
- `get_account_info` — מידע חשבון

## דרישות

- NinjaTrader 8 מותקן ופועל
- Node.js v18+
- חיבור ל-Tradovate דרך NinjaTrader
