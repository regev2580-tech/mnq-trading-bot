# Backtests — בדיקות היסטוריות

בדיקות היסטוריות לאסטרטגיות ICT 2022 על MNQ1!.

## קבצים

| קובץ | אסטרטגיה | טווח זמן |
|------|----------|---------|
| `ict_backtest.py` | ICT בסיסי — OB + FVG | M15 |
| `ict_1h_backtest.py` | ICT על גרף שעתי | H1 |
| `ict_backtest_daily.py` | ICT עם bias יומי | D1 → M15 |
| `ict_pro_backtest.py` | גרסה מלאה — כל הפילטרים | M5/M15 |

## הרצה

```bash
# בדיקה בסיסית
python backtests/ict_backtest.py

# גרסה מקצועית עם כל הפילטרים
python backtests/ict_pro_backtest.py
```

## מדדי הערכה

- Win Rate מינימום: 50%
- R:R מינימום: 1:2
- Max Drawdown: מתחת ל-5%
- Profit Factor: מעל 1.5

## הערות

- כל הבדיקות על נתוני MNQ1! היסטוריים
- פילטר Kill Zone פעיל (רק NY AM)
- SL ו-TP מחושבים לפי מבנה שוק
