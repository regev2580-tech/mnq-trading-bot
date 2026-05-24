# Trade Journal — יומן עסקאות

תיעוד כל העסקאות עם ניתוח ביצועים.

## קבצים

| קובץ | תיאור |
|------|-------|
| `trade_log.json` | כל העסקאות בפורמט JSON מובנה |

## מבנה trade_log.json

```json
{
  "account": { "name", "broker", "instrument", "point_value" },
  "trades": [
    {
      "id": 1,
      "date": "YYYY-MM-DD",
      "session": "NY AM Kill Zone",
      "direction": "LONG/SHORT",
      "entry": 0.0,
      "sl": 0.0,
      "tp1": 0.0,
      "exit": 0.0,
      "r": 2.0,
      "pnl_usd": 0.0,
      "outcome": "WIN/LOSS/BE",
      "setup": { "type", "confirmation", "mistakes" }
    }
  ]
}
```

## סטטיסטיקות נוכחיות

| מדד | ערך |
|-----|-----|
| סה"כ עסקאות | 6 |
| נצחונות | 1 |
| הפסדים | 4 |
| BE | 1 |
| Win Rate | ~17% |

## כללי יומן

- כל עסקה חייבת לכלול: setup, confirmation, mistakes
- תיעוד מיידי אחרי יציאה מעסקה
- ניתוח שבועי — מה עבד, מה לא
