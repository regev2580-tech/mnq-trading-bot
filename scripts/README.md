# Scripts — סקריפטי הפעלה

סקריפטי עזר להפעלת מערכת המסחר.

## קבצים

| קובץ | תיאור |
|------|-------|
| `launch_tradingview_debug.bat` | פתיחת TradingView במצב debug עם CDP |

## שימוש

### הפעלה יומית (סדר מומלץ)

```
1. הרץ: scripts\launch_tradingview_debug.bat
2. פתח Claude Code מחדש
3. כתב: "תבצע tv_health_check"
4. המתן לאישור חיבור
5. התחל ניתוח
```

### הסבר launch_tradingview_debug.bat

מפעיל את TradingView עם פורט CDP 9222 לצורך:
- חיבור Claude לגרף בזמן אמת
- צילום screenshots אוטומטי
- קריאת נתוני מחיר

## דרישות

- TradingView Desktop גרסה 3.1.0.7818+
- Claude Code מותקן
- tradingview-mcp פעיל
