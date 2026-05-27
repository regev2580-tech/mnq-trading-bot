# /tv-analysis — ניתוח MTF מלא של TradingView

מבצע ניתוח Daily→4H→1H→15M→5M ומחזיר bias מלא + רמות + תרחישים ל-Kill Zone.

## רצף הפעולות

### שלב 1: מצב גרף + מחיר (בו-זמנית)
```
tv_health_check          → ודא חיבור
chart_get_state          → symbol, timeframe, שמות indicators
quote_get                → מחיר נוכחי
```

### שלב 2: קרא Pine Indicator Levels (לפני החלפת TF!)
קרא את הרמות שה-indicators של המשתמש מצייר על הגרף:
```
data_get_pine_labels     → רמות עם תוויות (PDH, PDL, OB, FVG, PSP, MES11, etc.)
data_get_pine_lines      → קווים אופקיים ממחשב
data_get_pine_tables     → טבלאות analytics אם יש
```
⚠️ חובה: indicators חייבים להיות גלויים על הגרף כדי שזה יעבוד.

### שלב 3: Daily (20 נרות)
```
chart_set_timeframe("D")
data_get_ohlcv(count=20)           → 20 ימים אחרונים
capture_screenshot(region="chart", filename="daily_analysis")
```
**לנתח:** trend direction, PDH/PDL, האם מחיר ב-premium (מעל EQ) או discount (מתחת), שבירת highs/lows.

### שלב 4: 1H (24 נרות = 24 שעות)
```
chart_set_timeframe("60")
data_get_ohlcv(count=24)
capture_screenshot(region="chart", filename="1h_analysis")
```
**לנתח:** market structure, trend היומי, session range, order blocks ב-1H.

### שלב 5: 15M (32 נרות = ~8 שעות)
```
chart_set_timeframe("15")
data_get_ohlcv(count=32)
capture_screenshot(region="chart", filename="15m_analysis")
```
**לנתח:** מבנה Kill Zone האחרונה, FVGs, momentum לפני הכניסה.

### שלב 6: חזרה ל-5M (base chart)
```
chart_set_timeframe("5")
data_get_ohlcv(count=20, summary=true)
capture_screenshot(region="full", filename="5m_final")
```

## מסגרת ניתוח — ICT 2022 Method

### Bias Decision Tree
```
Daily premium? → SHORT bias preferred (מכירה מהRejection)
Daily discount? → LONG bias preferred (קנייה מהSupport)
Daily mid-range? → follow 1H trend
```

### רמות Key לחפש
| רמה | מה זה |
|-----|--------|
| PDH / PDL | Previous Day High/Low — liquidity targets |
| PWH / PWL | Previous Week High/Low |
| CDH / CDL | Current Day High/Low |
| OB | Order Block — נר לפני move גדול |
| FVG | Fair Value Gap — פער מחירים לא מלא |
| PSP | Potential Setup Point — נקודת כניסה אפשרית |
| EQ | Equilibrium = 50% של range |
| OTE | Optimal Trade Entry = 61.8-78.6% retracement |

### Kill Zone — NY AM
- **ישראל:** 16:30-18:00 (UTC+3 קיץ)
- **UTC:** 13:30-15:00
- **NY:** 09:30-11:00 ET
- זה הזמן שבו המוסדיים נכנסים — הגבוה ביותר לסטאפים

### תרחישים שיוצגו בדוח
1. **LONG setup**: מחיר ↓ ל-OTE/discount/support + bull orderflow → LONG
   - כניסה, SL (מתחת ל-structure), TP (PDH/CDH), R/R
2. **SHORT setup**: מחיר ↑ ל-premium/resistance/OB + bear orderflow → SHORT
   - כניסה, SL (מעל ל-structure), TP (PDL/CDL), R/R
3. **Wait**: אין setup ברור

## פורמט הדוח הסופי

```
## MTF Analysis — [SYMBOL] | [TIME] Israel

### DAILY → [BULL/BEAR/RANGE]
- Last close vs PDH/PDL
- Key daily levels

### 1H → [BULL/BEAR]
- Session structure
- Recent swing H/L

### 15M → [momentum direction]
- Recent move description

### 5M → [current price vs levels]

### Pine Indicator Levels
- [כל הרמות שנקראו מה-indicators]

### Kill Zone Setups (16:30-18:00 Israel)
LONG: entry X | SL X | TP X | R/R 1:X → trigger: [תנאי]
SHORT: entry X | SL X | TP X | R/R 1:X → trigger: [תנאי]
```
