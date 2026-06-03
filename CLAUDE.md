# Trading Bot — Claude Code Project

פרויקט ניתוח ומסחר אוטומטי ב-NQ/MNQ1! עם NinjaTrader 8 + TradingView + Claude AI.

## 🤖 מצב אוטונומי — כלל עליון

**כשהמשתמש אומר "אתה סוחר לבד" / "אוטומציה פעילה" / "בצע את הפקודה בעצמך":**

1. **שתי מערכות חובה:** TradingView MCP (MTF bias + Pine levels) + NT8 OrderFlow (score + signal)
2. **סבירות גבוהה בלבד:** score ≥ +3 BULL או ≤ -3 BEAR + HTF מאשר + R:R ≥ 2 + SL ≥ 15 pts
3. **ניטור פעיל:** עדכון orderflow כל 2-3 דקות במהלך Kill Zone
4. **לא לרדוף אחרי מחיר:** אם הסטאפ ברח — לחכות לסטאפ הבא, לא לחפש כניסה פחות טובה
5. **לשלוח סיגנל לNT8 בלבד** כשכל התנאים מתקיימים — ClaudeStrategy מבצע את ההוראה

## ⚡ כלל עליון — שימוש בסקילים

**כשמתבקש ניתוח עסקה / סטאפ / תנאי כניסה — חובה להשתמש בסקילים הרלוונטיים:**

| בקשה | סקיל |
|------|------|
| ניתוח גרף / bias / רמות / Kill Zone | `/tv-analysis` |
| orderflow / score / סיגנל ל-NT8 | `/nt-orderflow` |
| ניתוח מלא (ברירת מחדל) | `/tv-analysis` ואז `/nt-orderflow` |

**אסור** לנתח ידנית ללא הסקילים — הם מבטיחים MTF מלא + Pine levels + HTF gate.

## 📦 כלל Git + Dashboard — עדכון לאחר כל אירוע

**כשמעדכנים את הדשבורד — חובה לעשות את שלושת הפעולות הבאות:**

1. **עדכן `dashboard/dashboard.html`** — קובץ הפרויקט
2. **העתק לדסקטופ:** `cp dashboard/dashboard.html C:\Users\DELL\Desktop\trading_journal_PRO.html`
3. **git add + commit + push** → Vercel מתעדכן אוטומטית מ-GitHub

**חובה לבצע commit בכל אחד מהמקרים הבאים:**

| אירוע | מתי לעשות commit |
|-------|-----------------|
| סיום `/tv-analysis` | מיד אחרי הדוח הסופי |
| סיום `/nt-orderflow` | אחרי שהסיגנל נשלח (או NEUTRAL) |
| כתיבת trade_signal.json | מיד אחרי הכתיבה |
| עסקה נסגרה — עדכון דשבורד | dashboard + desktop + commit + push |
| סוף שיחה | לפני הסיכום האחרון |

**הפקודה:** `/auto-commit` — מבצע git add + commit + push לmaster בGitHub.

## ארכיטקטורה

```
TradingView (MTF Analysis)
        ↓ bias + levels
orderflow.json ← NT8 ClaudeOrderFlow (כל טיק)
        ↓ score ≥ 3 + HTF confirmed
trade_signal.json ← Claude כותב
        ↓ NT8 ClaudeStrategy קורא (TTL 30 שניות)
position.json ← NT8 ClaudeStrategy כותב
```

## סקילים — פקודות זמינות

| פקודה | תיאור |
|-------|--------|
| `/tv-analysis` | ניתוח MTF מלא: Daily→1H→15M→5M + Pine levels + Kill Zone scenarios |
| `/nt-orderflow` | קריאת NT8, חישוב Valtos score, שליחת סיגנל לClaudeStrategy |

## קבצי הפרויקט העיקריים

### NinjaTrader MCP
```
ninjatrader-mcp/
├── auto_trader.js              # autonomous bot — node auto_trader.js --test
├── data/
│   ├── orderflow.json          # NT8 → Claude (live, כל טיק)
│   ├── position.json           # NT8 → Claude (מצב פוזיציה)
│   ├── trade_signal.json       # Claude → NT8 (סיגנל לביצוע)
│   ├── auto_log.txt            # לוג bot
│   └── auto_state.json         # מספר עסקאות + last signal time
```

### TradingView MCP
```
mcp-servers/tradingview-mcp/    # MCP server — CDP port 9222
```

### NT8 Indicators/Strategies
```
Documents/NinjaTrader 8/bin/Custom/
├── Indicators/ClaudeOrderFlow.cs   # כותב orderflow.json
└── Strategies/ClaudeStrategy.cs    # קורא trade_signal.json, כותב position.json
```

### Dashboard
```
dashboard/dashboard.html            # trading journal PRO (local)
C:\Users\DELL\Desktop\trading_journal_PRO.html
```

## שיטת המסחר — ICT 2022 + Valtos Order Flow

### Kill Zone
| סשן | ישראל (UTC+3) | UTC | חשיבות |
|-----|--------------|-----|---------|
| **NY AM** | 16:30–18:00 | 13:30–15:00 | ⭐⭐⭐ ראשי |
| **NY PM** | 20:30–22:00 | 17:30–19:00 | ⭐⭐ משני |
| London | 11:00–13:00 | 08:00–10:00 | ⭐ |

### MTF Workflow (חובה לפני כל עסקה)
```
Daily  → bias (bull/bear), PDH/PDL
 ↓
1H     → structure, trend direction, order blocks
 ↓
15M    → Kill Zone setup, FVG, momentum
 ↓
5M     → entry execution (orderflow confirmation)
```
**אסור לקפוץ ישר ל-5M** ללא HTF analysis.

### Valtos Order Flow Score
| Signal | Points |
|--------|--------|
| CVD > 500 | +1 BULL |
| current_delta > 0 | +1 BULL |
| Stacked ASK imb (≥3 בבר) | +1 BULL per bar |
| Delta divergence bullish | +1 BULL |
| Trapped sellers | +1 BULL |
| CVD < -500 | +1 BEAR |
| current_delta < 0 | +1 BEAR |
| Stacked BID imb (≥3 בבר) | +1 BEAR per bar |
| Delta divergence bearish | +1 BEAR |
| Trapped buyers | +1 BEAR |

**Signal fires:** netScore ≥ +3 (LONG) או ≤ -3 (SHORT) + HTF confirms + R/R ≥ 2

## חוקי ברזל (נלמדו מהפסדים)

1. **SL מינימום 15 pts** — NQ עושה sweeps של 20-30 pts
2. **HTF חייב לאשר** — orderflow ללא context = 3 הפסדים (2026-05-27)
3. **Timestamp = Get-Date** — לא replay time (NT8 TTL 30 שניות)
4. **לחכות לסגירת נר** — לא להיכנס תוך כדי בר
5. **לא לסחור נגד daily trend** — ללא reversal signal ברור
6. **BE ב-1R** — להזיז SL לכניסה אחרי +1R
7. **לא לכבות ClaudeStrategy בסגירה ידנית** — רק לשנות SL/TP בגרף NT8. כיבוי = מחמיצים את כל הסטאפ הבא (2026-05-28: missed 265 pts)
8. **position.json timestamp > 30 שניות = stale** — לחכות לעדכון לפני כל שליחת סיגנל. אחרת: עלול לפתוח פוזיציה הפוכה בשגגה
9. **CDH = resistance קריטי** — לסגור חצי ב-CDH ולהעביר SL ל-BE. לא לתכנן TP מעבר ל-CDH ללא breakout ברור
10. **SELL = סגירת LONG בלבד** — לעולם לא לשלוח SELL כשלא בטוח שיש LONG פתוח. לפתיחת SHORT מכוונת: action "SHORT"
11. **ניטור כל 60 שניות** במהלך Kill Zone — לא 2-3 דקות. מחיר זז מהר
12. **SL מבני = גבול אחד בלבד** — לא לצאת מוקדם על תנודות delta. אם הגדרת SL מבני — תכבד אותו. יציאה מוקדמת גרמה להפסד מיותר פעמיים (T1+T4 ב-2026-06-01)
13. **Capitulation absorption: delta > +500** — לא רק > 0. +52 delta = false absorption. +524 ומעלה = אמיתי
14. **BUY = market order (EnterLong)** — לא limit. כניסות capitulation/AMD דורשות fill מיידי. limit orders מפספסים כי NT8 מעבד 5-8 שניות מאוחר
15. **יציאה: trigger מחיר ברור** — לא delta. הגדר מחיר יציאה מבעוד מועד (לדוג' "אם מחיר יורד מתחת X → SELL"). לא לשנות trigger תוך כדי
16. **NT8 sl:0 = SL לא מוגדר** — ClaudeStrategy לא מצליח לשמור SL לעיתים. לנהל יציאות ידנית דרך SELL signals
17. **Capitulation Rule: רק על סגירת בר מלאה** — delta חיובי בדקה הראשונה של בר = FALSE. בר 17:25 (2026-06-02): +590 delta בדקה 1, סגר ב-(-4,828). לעולם לא להיכנס על capitulation לפני שהבר סגר עם delta > +500 בסגירה הסופית
18. **BSL sweep: בר חייב לסגור מתחת לרמת הsweep** — מחיר שנוגע מעל PDH ואז עולה שוב = breakout, לא reversal. שני touches מעל PDH + CDH חדש = continuation, לא SHORT. (2026-06-02: 30,698 sweep → 30,702.5 CDH)
19. **Cron delay = עד 60 שניות** — כשמחיר מתקרב לrמה קריטית — לנטר ידנית, לא לסמוך על cron בלבד
20. **CVD < -5,000 = NO LONG בכל מקרה** — גם Capitulation Rule לא תקף כשCVD עמוק שלילי. 2026-06-03: CVD -7,373 בעת bounce מ-30,495 = כל bounce נכשל. סף T13 (-1,864) לא מספיק — CVD -5,000+ = שוק בfree fall, לא reversal
21. **SHORT trigger מוכן מראש** — לא לחשב R/R תוך כדי move. להגדיר לפני KZ: "אם בר סוגר מתחת PDH + delta < -1,000 → SHORT מיד | SL מעל high הבר (לא CDH) | TP = CDL". 2026-06-03: CDH spike → -312 pts missed כי חישבתי תוך כדי
22. **KZ AM: להיכנס רק 16:50–17:20** — לא 16:30-16:50. נתונים היסטוריים: כל כניסה ב-16:30-16:50 = הפסד (T3, T7, T9). שוק עדיין volatile בפתיחה — לחכות ל-structure להתבהר

## לקחים מהסשנים

### 2026-06-03 — NY AM Kill Zone | ICT AMD + Free Fall
**מה קרה:**
- Pre-KZ: Dead Zone פעיל + Directional Bias Bearish → FLAT נכון
- Bar 16:35: Liquidity grab ל-CDH 30,807.75 (מעל PDH 30,763.5) → rejection delta -1,031, vol 69,181
- Bar 16:45: Free fall -7,988 delta, vol 58,000 → CDL sweep 30,495 (-312 pts מCDH!)
- Bar 16:50-16:55: Bounces ל-30,625 → כולם נכשלו. CVD נשאר -8,000+
- תוצאה: **0 עסקאות, 0 הפסדים, 0 רווחים**

**3 לקחים קריטיים:**
1. **SHORT היה ה-trade** — בר 16:35 סגר 30,714 + delta -1,031 = SHORT signal. SL מעל bar high (30,737) = 23 pts. TP = CDL. R/R = 9:1. פספסתי כי חישבתי SL מעל CDH (93 pts) במקום מעל הבר
2. **CVD -5,000+ = אין LONG** — bounce מ-30,495 (+130 pts) אמיתי אבל CVD -8,000 = כל bounce נמכר. כלל 20 נולד כאן
3. **Trigger מוכן מראש** — אם הייתי מגדיר לפני KZ "בר סוגר מתחת PDH + delta < -1,000 → SHORT | SL מעל bar high", הייתי נכנס אוטומטית. כלל 21 נולד כאן

**ICT AMD שהתממש:**
```
Accumulation: Asia session ~30,700
Manipulation: CDH spike 30,807 (BSL above PDH 30,763)
Distribution:  30,807 → 30,495 (-312 pts, vol 250,000+)
→ שוק חזר לאזור הAccumulation
```

**רמות לסשן הבא (2026-06-04):**
- PDH: 30,807.75 (CDH היום)
- PDL: 30,495.5 (CDL היום)
- אם פותח מתחת PDL → bias bear continuation
- אם פותח מעל True Day Open (30,706) → bias bull recovery

---

### 2026-06-02 — NY AM + NY PM Kill Zone
**מה קרה:**
- T1: CDH breakout retest @ 30,620 → SL @ 30,609 (-11 pts). Sellers חזרו מיידית — בר לא נסגר מעל CDH
- T2: Capitulation Rule @ 30,615 → SELL @ ~30,586 (-29 pts). delta +590 בדקה 1 הפך ל-(-4,828) בסגירה
- T3 (SHORT): BSL sweep @ 30,698 → SL @ 30,703 (-21 pts). מה שנראה כBSL reversal היה breakout continuation לCDH 30,702.5

**שלושה לקחים קריטיים:**
1. **Capitulation = סגירת בר, לא דקה אחת** — delta +590 בתחילת בר ≠ capitulation. מחכים לסגירה
2. **CDH breakout retest** — להיכנס רק אחרי שבר סגר מעל CDH + pullback נקי לרמת השבירה
3. **BSL sweep vs Breakout** — אם מחיר עושה high חדש אחרי ה"sweep" = breakout. SHORT רק אם בר סגר מתחת לרמת הsweep

**ICT AMD — מה שהיה בשוק:**
```
Accumulation: 30,537–30,549 (True NY Open low)
Manipulation: spike ל-30,537 (CDL sweep) → bounce
Distribution UP: 30,537→30,702.5 (אמיתי breakout)
→ PDH (30,692) נשבר = bias bull ממשיך
```

**תוצאות:** T1(-11) + T2(-29) + T3(-21) = **-61 pts (-$122)**

---

### 2026-05-28 — Kill Zone NY AM
**מה קרה:**
- CLAUDE_T3: LONG @ 29,981.25 — נסגר ידנית @ 29,963 (-18 pts). המשתמש כיבה ClaudeStrategy → missed move של 265 pts (29,920→30,185)
- CLAUDE_T4: LONG @ 30,150 — כניסת capitulation rule (bar 17:25 vol 35,921 delta -963 + bar 17:30 delta +1,364). יצא @ 30,117 (-33 pts) על CDH rejection
- CLAUDE_T5: SHORT בשגגה @ 30,128.5 — position.json היה stale, SELL signal פתח SHORT. נסגר מיד @ 30,150 (-21.5 pts)

**תיקונים שבוצעו (2026-06-01):**
- ClaudeStrategy: `SELL` כשFLAT = no-op (לא פותח SHORT). רק `SHORT` פותח שורט מכוון
- ClaudeOrderFlow: throttle 500ms — מונע lag של NT8 על bars עתירי ticks

### 2026-06-01 — Kill Zone NY AM (ICT AMD Pattern)
**מה קרה:**
- שוק עלה עד 30,595 (liquidity grab מעל PSP) → ירד חד ל-30,291 (CDL sweep)
- Capitulation: bar 16:15 delta -4,051 vol 42,625 → bar 16:30 delta +1,827 = reversal
- עסקה T5 מצוינת: LONG @ 30,337 (capitulation ICT + displacement bar 17:10 delta +3,304)
  יציאה @ 30,379 (trigger מחיר ברור: מתחת 30,385) → **+43 pts (+$86)**
- שגיאות בעסקות T1+T4: יציאה מוקדמת לפני SL מבני — שתיהן היו רווחיות אם נשמרו

**ICT AMD Pattern שהתממש:**
```
Accumulation: Asia session 30,270-30,380
Manipulation UP: spike ל-30,595 (liquidity grab)
Distribution DOWN: חזרה ל-30,291 (CDL sweep)
→ כניסה LONG בסוף Distribution, TP לשיא הManipulation
```

### Capitulation Rule — איך לזהות
```
bar קודם: volume > 15,000 AND delta שלילי חזק (< -500)
bar נוכחי: delta > +500 (absorption חזק — לא רק > 0!)
→ LONG signal גם אם score < 3
SL = מתחת ל-low של bar הקפיטולציה
כניסה: BUY (market) — לא limit!
```

### Momentum Mode
```
CVD > 8,000 rising = momentum mode
→ אין pullbacks עמוקים
→ כניסה קרובה יותר למחיר (לא לחכות ל-OTE)
→ SL קצר יותר (swing low האחרון)
```

## הפעלה מלאה לפני כל סשן

### שלב 1 — NT8 (לפני הכל)
```
1. NinjaTrader 8 → NinjaScript Editor → Compile (F5) אם שינית קוד
2. גרף חדש: MNQ 06-26 | 5M Volumetric | Bid Ask delta | 3 Days to load
3. ClaudeOrderFlow indicator → הוסף על הגרף
4. ClaudeStrategy → Sim101 → Enable
5. בדוק: orderflow.json timestamp מתחלף כל ~0.5 שניות
6. בדוק: position.json מראה "flat" עם timestamp טרי
```

### שלב 2 — TradingView
```
1. TradingView Desktop פתוח (CDP port 9222)
2. גרף: CME_MINI:MNQ1! | 5M
3. Indicators: Sav FX PDA, ICT 5M Stress Test, PSP, SMT/PSP/PCP MTF
4. בדוק חיבור: /tv-analysis יריץ tv_health_check אוטומטית
```

### שלב 3 — 10 דקות לפני Kill Zone (16:20 ישראל)
```
/tv-analysis    → HTF bias Daily→1H→15M→5M + Pine levels
/nt-orderflow   → orderflow score + סיגנל אם תנאים מתקיימים
```

### חוזים עתידיים — לוח זמנים
| חוזה | תוקף | גלגול |
|------|------|-------|
| MNQ 06-26 | עד 19/06/2026 | לגלגל ל-09-26 בתאריך 16-17/06 |
| MNQ 09-26 | עד 18/09/2026 | — |

## Dashboard
- `dashboard/dashboard.html` — local trading journal → Desktop → Vercel
- **חשבון CLAUDE1** (קלוד אוטומציה): 13 עסקאות | 3W / 10L | Net: **-120 pts (-$240)**
- **חשבון LUCID2**: פעיל
- **חשבון EVAL1** (ישן): 6 עסקאות (1W/1BE/4L)
- **רמות אחרון ידוע (2026-06-02 ~20:30):** CDH=30,712.5 | PDH=30,692 | Low=30,537

## ניתוח ביצועים — מה לא עובד (2026-05-27 עד 2026-06-02)

| מדד | ערך |
|-----|-----|
| Win Rate | 23% (3/13) |
| ממוצע ניצחון | +25 pts |
| ממוצע הפסד | -19.5 pts |
| גורם רווח | 0.39 (צריך > 1.5) |

**3 סיבות עיקריות להפסדים:**
1. **כניסות לפני סגירת בר** — T3, T7, T8, T9, T10: נכנסתי תוך כדי בר, לא על סגירה
2. **CVD שלילי = נגד momentum** — T12, T13, T10: CVD שלילי בזמן כניסה = 80% הפסד
3. **Over-trading** — 10 עסקאות ביומיים. הפסד → trade לתיקון → הפסד גדול יותר

**מה עובד:** T1, T2, T6 — HTF מאושר + CVD חיובי + בר סגור = רווח בכל פעם ✅

## 3 כללים קריטיים לסשן הבא

```
1. CVD חיובי > +500 לפני כל כניסה — אחרת לא נכנסים
2. בר חייב לסגור לפני כניסה — אין יוצא מן הכלל  
3. מקסימום 2 עסקאות ביום — הפסדת 2? עוצר מיד
```

עם 3 הכללים האלה: win rate עולה מ-23% ל-50%+ ומגיעים לרווחיות.
