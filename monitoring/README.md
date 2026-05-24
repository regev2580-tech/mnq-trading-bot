# Monitoring — ניטור בזמן אמת

ניטור NY Kill Zone ואיתותי כניסה בזמן אמת.

## קבצים

| קובץ | תיאור |
|------|-------|
| `ny_monitor.py` | ניטור NY AM Kill Zone (09:30–11:00 EST) |

## הפעלה

```bash
python monitoring/ny_monitor.py
```

## מה מנוטר

- ⏰ NY AM Kill Zone: 09:30–11:00 EST (16:30–18:00 שעון ישראל)
- 📍 Order Blocks ב-H1/M15
- 💧 Liquidity Sweeps
- 🔲 Fair Value Gaps (FVG)
- 📊 Volume Delta

## התראות

המערכת שולחת התראה כאשר:
1. המחיר מגיע ל-Order Block ב-Kill Zone
2. FVG נסגר חלקית
3. Liquidity נלקחת לפני היפוך
