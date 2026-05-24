# Dashboard — דשבורד מסחר

דשבורד ויזואלי למעקב אחר ביצועי המסחר ב-MNQ1!.

## קבצים

| קובץ | תיאור |
|------|-------|
| `dashboard.html` | דשבורד סטטי — נפתח ישירות בדפדפן |
| `dashboard.py` | שרת Python להצגת הדשבורד |
| `generate_dashboard.py` | יצירת דשבורד מ-trade_log.json |

## שימוש

### פתיחה מהירה (HTML סטטי)
```
פתח את dashboard.html ישירות בדפדפן
```

### הפעלה עם Python
```bash
python dashboard.py
```

### יצירת דשבורד מעודכן
```bash
python generate_dashboard.py
```

## תכונות

- 📊 עקומת רווח/הפסד
- 📈 Win Rate ו-R:R ממוצע
- 📅 ביצועים לפי יום/שבוע
- 🎯 ניתוח לפי סוג Setup
- ⚡ ניטור Kill Zones

## דיפלוי

הדשבורד רץ ב-Vercel: [https://trading-bot-dashboard.vercel.app](https://trading-bot-dashboard.vercel.app)
