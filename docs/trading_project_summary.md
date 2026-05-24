# פרויקט מסחר אוטומטי — סיכום מעודכן

## המטרה:
בניית מערכת שבה Claude AI רואה את גרף TradingView בזמן אמת ומייעץ/מסחר.

## פרטי החשבון:
- **ברוקר:** Tradovate
- **חשבון:** LFE0505997545001 (Eval) + LFE02559975450002 (Eval)
- **חברת Prop:** Lucid Trader (אישרו שימוש באוטומציה)
- **נכס:** MNQM6 (Micro Nasdaq Futures)
- **TradingView:** גרסה 3.1.0.7818 מותקנת

## מה מותקן:
- Python 3.14.5 ✅
- Node.js v24.15.0 ✅
- Git 2.54.0 ✅
- TradingView MCP Server ✅ (C:\Users\DELL\New folder\tradingview-mcp)
- TradingView debug mode ✅
- Claude API — עדיין חסר ⏳

## קבצים חשובים:
- MCP Config: C:\Users\DELL\.claude\mcp.json
- הפעלת TradingView debug: C:\Users\DELL\New folder\launch_tradingview_debug.bat

## איך להפעיל בכל פעם:
1. פתח cmd והרץ: "C:\Users\DELL\New folder\launch_tradingview_debug.bat"
2. פתח Claude Code מחדש
3. כתוב: "תבצע tv_health_check"

## הארכיטקטורה שנבנה:
```
TradingView (נתוני מחיר) → Webhook → Python Server → Claude API → Tradovate → עסקה
```

## האסטרטגיות שישמש Claude:
- ICT 2022 (Order Blocks, FVG, Liquidity, Kill Zones)
- Wyckoff (Accumulation/Distribution)
- תורת הרבעים
- Price Action / SMC
- Order Flow

## סגנון מסחר:
- 1-2 עסקאות איכותיות ביום בלבד (לא הרבה עסקאות)
- רק הגדרות A+
- SL ו-TP מחושבים לפי מבנה השוק

## השלבים הבאים:
1. סיים רכישת Claude API Key ב-console.anthropic.com
2. שדרג TradingView ל-Plus (לצורך Webhooks)
3. בניית MCP Server
4. חיבור הכל יחד
5. בדיקה על Demo חודש לפני לייב

## איך להמשיך בשיחה חדשה:
כתוב: "תקרא את קובץ trading_project_summary.md מהתיקייה New folder"
