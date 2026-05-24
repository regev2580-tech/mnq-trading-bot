#!/usr/bin/env python3
"""
מחולל דשבורד מסחר מקצועי - MNQ1!
מעדכן את dashboard.html מתוך trade_log.json
"""
import json, statistics, webbrowser
from datetime import datetime

LOG_FILE  = r"C:\Users\DELL\New folder\trade_log.json"
HTML_FILE = r"C:\Users\DELL\New folder\dashboard.html"

def load():
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def generate():
    data   = load()
    acc    = data["account"]
    trades = data["trades"]

    wins   = [t for t in trades if t["outcome"] == "WIN"]
    losses = [t for t in trades if t["outcome"] == "LOSS"]
    bes    = [t for t in trades if t["outcome"] == "BREAKEVEN"]
    total  = len(trades)
    wr     = round(len(wins)/total*100, 1) if total else 0
    total_r   = round(sum(t["r"] for t in trades), 2)
    total_pts = round(sum(t["pts"] for t in trades), 1)
    total_usd = round(sum(t["pnl_usd"] for t in trades), 2)

    eq, peak, max_dd = 0, 0, 0
    equity_points = [0]
    for t in trades:
        eq += t["r"]; peak = max(peak, eq)
        max_dd = max(max_dd, peak - eq)
        equity_points.append(round(eq, 2))

    pf  = round(sum(t["r"] for t in wins) / abs(sum(t["r"] for t in losses)), 2) if wins and losses else 0
    exp = round((wr/100 * statistics.mean(t["r"] for t in wins)) - ((1-wr/100) * statistics.mean(abs(t["r"]) for t in losses)), 2) if wins and losses else 0
    avg_win_pts  = round(statistics.mean(t["pts"] for t in wins), 1) if wins else 0
    avg_loss_pts = round(statistics.mean(abs(t["pts"]) for t in losses), 1) if losses else 0

    sessions = {}
    for s in ["London Kill Zone", "NY AM Kill Zone"]:
        st = [t for t in trades if t["session"] == s]
        sw = [t for t in st if t["outcome"] == "WIN"]
        if st:
            sessions[s] = {
                "count": len(st), "wins": len(sw),
                "wr": round(len(sw)/len(st)*100,1),
                "r": round(sum(t["r"] for t in st),2),
                "pts": round(sum(t["pts"] for t in st),1)
            }

    directions = {}
    for d in ["LONG","SHORT"]:
        dt = [t for t in trades if t["direction"] == d]
        dw = [t for t in dt if t["outcome"] == "WIN"]
        if dt:
            directions[d] = {
                "count": len(dt), "wins": len(dw),
                "wr": round(len(dw)/len(dt)*100,1),
                "r": round(sum(t["r"] for t in dt),2)
            }

    SESSION_HE = {"London Kill Zone": "London", "NY AM Kill Zone": "NY AM"}
    DIR_HE = {"LONG": "לונג", "SHORT": "שורט"}
    OUTCOME_HE = {"WIN": "רווח", "LOSS": "הפסד", "BREAKEVEN": "נקודת איזון"}

    trade_rows = ""
    for t in trades:
        if t["outcome"] == "WIN":
            badge = '<span class="badge win">רווח</span>'
        elif t["outcome"] == "LOSS":
            badge = '<span class="badge loss">הפסד</span>'
        else:
            badge = '<span class="badge be">איזון</span>'

        pts_color = "pos" if t["pts"] >= 0 else "neg"
        sign = "+" if t["pts"] >= 0 else ""
        rsign = "+" if t["r"] >= 0 else ""
        usign = "+" if t["pnl_usd"] >= 0 else ""
        mistake = f'<div class="mistake">&#9888; {t["management"]["mistake"]}</div>' if t["management"].get("mistake") else ""
        good    = f'<div class="good">&#10003; {t["management"]["good_decision"]}</div>' if t["management"].get("good_decision") else ""
        session_he = SESSION_HE.get(t["session"], t["session"])

        trade_rows += f"""
        <tr>
          <td><span class="trade-id">#{t['id']}</span></td>
          <td>{t['date']}<br><small>{t['time_entry']}</small></td>
          <td><small>{session_he}</small></td>
          <td><span class="dir {t['direction'].lower()}">{DIR_HE.get(t['direction'], t['direction'])}</span></td>
          <td>{t['contracts']}</td>
          <td>{t['entry']}</td>
          <td>{t['sl']}</td>
          <td>{t['exit']}<br><small>{t['exit_type']}</small></td>
          <td>{t['risk_pts']}</td>
          <td class="{pts_color}">{sign}{t['pts']}</td>
          <td class="{pts_color}">{rsign}{t['r']}R</td>
          <td class="{pts_color}">${usign}{t['pnl_usd']}</td>
          <td><span class="score">{t['setup']['score']}</span></td>
          <td>{badge}</td>
        </tr>
        <tr class="detail-row">
          <td colspan="14">
            <div class="detail-box">
              <div class="detail-setup"><b>סטאפ:</b> {t['setup']['trigger']}</div>
              <div class="detail-confluence"><b>קונפלואנס:</b> {' &bull; '.join(t['setup']['confluence'])}</div>
              {mistake}{good}
              <div class="lesson"><b>לקח:</b> {t['lesson']}</div>
            </div>
          </td>
        </tr>"""

    session_cards = ""
    for name, s in sessions.items():
        he = SESSION_HE.get(name, name)
        session_cards += f"""
        <div class="breakdown-row">
          <div class="br-name">{he}</div>
          <div class="br-wr" style="color:var(--{'green' if s['r']>0 else 'red'})">{s['wr']}%</div>
          <div class="br-detail">{s['count']} עסקאות &bull; {'+' if s['r']>=0 else ''}{s['r']}R &bull; {'+' if s['pts']>=0 else ''}{s['pts']} נק'</div>
        </div>"""

    direction_cards = ""
    for d, v in directions.items():
        direction_cards += f"""
        <div class="breakdown-row">
          <div class="br-name">{DIR_HE.get(d,d)}</div>
          <div class="br-wr" style="color:var(--{'green' if v['r']>0 else 'red'})">{v['wr']}%</div>
          <div class="br-detail">{v['count']} עסקאות &bull; {'+' if v['r']>=0 else ''}{v['r']}R</div>
        </div>"""

    eq_labels = [f"T{i}" for i in range(len(equity_points))]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>דשבורד מסחר — MNQ1!</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  :root {{
    --bg:      #0b0e17;
    --card:    #131722;
    --card2:   #161b29;
    --border:  #1e2535;
    --text:    #d1d4dc;
    --muted:   #6b7280;
    --green:   #00ff88;
    --red:     #ff4757;
    --yellow:  #ffd32a;
    --blue:    #4c9be8;
    --orange:  #ff9f43;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:var(--bg); color:var(--text); font-family:'Segoe UI',Arial,sans-serif; font-size:14px; direction:rtl; }}

  /* HEADER */
  .header {{ background:linear-gradient(135deg,#131722 0%,#0f1520 100%); border-bottom:1px solid var(--border); padding:20px 32px; display:flex; align-items:center; justify-content:space-between; }}
  .header-left h1 {{ font-size:22px; font-weight:800; color:#fff; }}
  .header-left h1 span {{ color:var(--blue); }}
  .header-left .subtitle {{ color:var(--muted); font-size:12px; margin-top:4px; }}
  .header-right {{ text-align:left; color:var(--muted); font-size:12px; line-height:1.8; }}
  .header-right b {{ color:var(--text); }}
  .live-dot {{ width:8px; height:8px; background:var(--green); border-radius:50%; display:inline-block; margin-left:6px; animation:pulse 2s infinite; }}
  @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:0.4}} }}

  .container {{ max-width:1440px; margin:0 auto; padding:24px 28px; }}

  /* KPI */
  .kpi-grid {{ display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin-bottom:22px; }}
  @media(max-width:1100px){{ .kpi-grid{{ grid-template-columns:repeat(3,1fr); }} }}
  .kpi {{ background:var(--card); border:1px solid var(--border); border-radius:14px; padding:20px 18px; position:relative; overflow:hidden; transition:transform .2s; }}
  .kpi:hover {{ transform:translateY(-2px); }}
  .kpi::after {{ content:''; position:absolute; bottom:0; left:0; right:0; height:3px; border-radius:0 0 14px 14px; }}
  .kpi.green::after {{ background:linear-gradient(90deg,var(--green),#00c868); }}
  .kpi.red::after   {{ background:linear-gradient(90deg,var(--red),#c0392b); }}
  .kpi.blue::after  {{ background:linear-gradient(90deg,var(--blue),#2980b9); }}
  .kpi.yellow::after{{ background:linear-gradient(90deg,var(--yellow),#e67e22); }}
  .kpi.orange::after{{ background:linear-gradient(90deg,var(--orange),#e17055); }}
  .kpi-icon  {{ font-size:22px; margin-bottom:10px; }}
  .kpi-label {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.8px; margin-bottom:6px; }}
  .kpi-value {{ font-size:30px; font-weight:800; line-height:1; }}
  .kpi-sub   {{ color:var(--muted); font-size:11px; margin-top:8px; }}
  .kpi.green .kpi-value  {{ color:var(--green); }}
  .kpi.red   .kpi-value  {{ color:var(--red); }}
  .kpi.blue  .kpi-value  {{ color:var(--blue); }}
  .kpi.yellow .kpi-value {{ color:var(--yellow); }}
  .kpi.orange .kpi-value {{ color:var(--orange); }}

  /* CHARTS */
  .charts-grid {{ display:grid; grid-template-columns:2.2fr 0.8fr; gap:16px; margin-bottom:22px; }}
  @media(max-width:900px){{ .charts-grid{{ grid-template-columns:1fr; }} }}
  .chart-card {{ background:var(--card); border:1px solid var(--border); border-radius:14px; padding:22px; }}
  .chart-title {{ font-size:12px; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:.8px; margin-bottom:18px; display:flex; align-items:center; gap:8px; }}
  .chart-title span {{ width:4px; height:16px; border-radius:2px; display:inline-block; }}
  .chart-title span.g {{ background:var(--green); }}
  .chart-title span.b {{ background:var(--blue); }}
  .chart-wrap {{ position:relative; height:210px; }}

  /* BREAKDOWN */
  .breakdown-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:22px; }}
  .breakdown-card {{ background:var(--card); border:1px solid var(--border); border-radius:14px; padding:20px; }}
  .breakdown-card h3 {{ font-size:12px; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:.8px; margin-bottom:16px; display:flex; align-items:center; gap:8px; }}
  .breakdown-card h3 span {{ width:4px; height:14px; border-radius:2px; display:inline-block; background:var(--blue); }}
  .breakdown-row {{ display:flex; align-items:center; gap:16px; padding:12px 0; border-bottom:1px solid rgba(255,255,255,0.04); }}
  .breakdown-row:last-child {{ border-bottom:none; }}
  .br-name {{ font-weight:700; font-size:14px; min-width:80px; }}
  .br-wr   {{ font-size:22px; font-weight:800; min-width:60px; }}
  .br-detail {{ color:var(--muted); font-size:12px; }}

  /* TABLE */
  .table-card {{ background:var(--card); border:1px solid var(--border); border-radius:14px; padding:22px; margin-bottom:22px; overflow-x:auto; }}
  .table-card h3 {{ font-size:12px; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:.8px; margin-bottom:18px; display:flex; align-items:center; gap:8px; }}
  .table-card h3 span {{ width:4px; height:14px; border-radius:2px; display:inline-block; background:var(--orange); }}
  table {{ width:100%; border-collapse:collapse; min-width:900px; }}
  th {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.5px; padding:10px 14px; text-align:right; border-bottom:2px solid var(--border); white-space:nowrap; }}
  td {{ padding:12px 14px; border-bottom:1px solid rgba(255,255,255,0.04); vertical-align:middle; }}
  td small {{ color:var(--muted); font-size:11px; display:block; margin-top:2px; }}
  tr:hover > td {{ background:rgba(255,255,255,0.025); cursor:pointer; }}
  .detail-row td {{ padding:0; border-bottom:none; }}
  .detail-row:hover td {{ background:transparent !important; cursor:default; }}

  .trade-id {{ background:rgba(76,155,232,0.15); color:var(--blue); padding:4px 10px; border-radius:8px; font-size:12px; font-weight:700; }}
  .dir.long  {{ color:var(--green); font-weight:800; background:rgba(0,255,136,0.1); padding:3px 10px; border-radius:6px; }}
  .dir.short {{ color:var(--red); font-weight:800; background:rgba(255,71,87,0.1); padding:3px 10px; border-radius:6px; }}
  .pos {{ color:var(--green); font-weight:700; }}
  .neg {{ color:var(--red); font-weight:700; }}
  .score {{ background:rgba(255,159,67,0.15); color:var(--orange); padding:3px 9px; border-radius:6px; font-size:12px; font-weight:700; }}

  .badge {{ padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700; }}
  .badge.win  {{ background:rgba(0,255,136,0.12); color:var(--green); border:1px solid rgba(0,255,136,0.3); }}
  .badge.loss {{ background:rgba(255,71,87,0.12);  color:var(--red);   border:1px solid rgba(255,71,87,0.3); }}
  .badge.be   {{ background:rgba(255,211,42,0.12); color:var(--yellow);border:1px solid rgba(255,211,42,0.3); }}

  .detail-box {{ padding:14px 18px; margin:0 0 1px; background:rgba(255,255,255,0.015); border-right:3px solid var(--blue); font-size:12px; }}
  .detail-setup      {{ color:var(--text); margin-bottom:5px; }}
  .detail-confluence {{ color:var(--blue); font-size:11px; margin-bottom:8px; }}
  .mistake {{ color:var(--red); margin:5px 0; padding:6px 10px; background:rgba(255,71,87,0.07); border-radius:6px; }}
  .good    {{ color:var(--green); margin:5px 0; padding:6px 10px; background:rgba(0,255,136,0.07); border-radius:6px; }}
  .lesson  {{ color:var(--yellow); margin-top:8px; padding:8px 10px; background:rgba(255,211,42,0.06); border-radius:6px; border-right:2px solid var(--yellow); }}

  /* RULES */
  .rules-card {{ background:var(--card); border:1px solid var(--border); border-radius:14px; padding:22px; margin-bottom:22px; }}
  .rules-card h3 {{ font-size:12px; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:.8px; margin-bottom:18px; display:flex; align-items:center; gap:8px; }}
  .rules-card h3 span {{ width:4px; height:14px; border-radius:2px; display:inline-block; background:var(--yellow); }}
  .rules-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
  @media(max-width:900px){{ .rules-grid{{ grid-template-columns:1fr; }} }}
  .rule {{ display:flex; align-items:flex-start; gap:12px; padding:12px 14px; background:rgba(255,255,255,0.02); border-radius:10px; border:1px solid rgba(255,255,255,0.04); }}
  .rule-num {{ background:var(--blue); color:#fff; border-radius:8px; padding:3px 10px; font-size:12px; font-weight:800; white-space:nowrap; min-width:32px; text-align:center; }}
  .rule-text {{ color:var(--text); font-size:13px; line-height:1.5; }}

  .footer {{ text-align:center; color:var(--muted); font-size:11px; padding:24px; border-top:1px solid var(--border); margin-top:8px; }}
  .footer b {{ color:var(--blue); }}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1><span class="live-dot"></span> דשבורד מסחר — <span>MNQ1!</span></h1>
    <div class="subtitle">Micro E-mini Nasdaq-100 Futures &nbsp;|&nbsp; ניתוח Claude AI</div>
  </div>
  <div class="header-right">
    <b>{acc['name']}</b><br>
    {acc['broker']} &nbsp;|&nbsp; שווי נקודה: ${acc['point_value']}<br>
    עדכון אחרון: {now}
  </div>
</div>

<div class="container">

  <div class="kpi-grid">
    <div class="kpi {'green' if total_r>=0 else 'red'}">
      <div class="kpi-icon">{'📈' if total_r>=0 else '📉'}</div>
      <div class="kpi-label">סה"כ R</div>
      <div class="kpi-value">{'+' if total_r>=0 else ''}{total_r}R</div>
      <div class="kpi-sub">{'+' if total_pts>=0 else ''}{total_pts} נקודות &nbsp;|&nbsp; ${'+' if total_usd>=0 else ''}{total_usd}</div>
    </div>
    <div class="kpi blue">
      <div class="kpi-icon">🎯</div>
      <div class="kpi-label">אחוז הצלחה</div>
      <div class="kpi-value">{wr}%</div>
      <div class="kpi-sub">{len(wins)} רווח &nbsp;/&nbsp; {len(losses)} הפסד &nbsp;/&nbsp; {len(bes)} איזון</div>
    </div>
    <div class="kpi {'green' if pf>=1.5 else 'yellow' if pf>=1 else 'red'}">
      <div class="kpi-icon">⚖️</div>
      <div class="kpi-label">Profit Factor</div>
      <div class="kpi-value">{pf}</div>
      <div class="kpi-sub">ממוצע רווח: +{avg_win_pts}נק' &nbsp;|&nbsp; ממוצע הפסד: -{avg_loss_pts}נק'</div>
    </div>
    <div class="kpi orange">
      <div class="kpi-icon">📊</div>
      <div class="kpi-label">Expectancy</div>
      <div class="kpi-value">{'+' if exp>=0 else ''}{exp}R</div>
      <div class="kpi-sub">ציפייה ממוצעת לעסקה</div>
    </div>
    <div class="kpi {'red' if max_dd>2 else 'yellow'}">
      <div class="kpi-icon">🛡️</div>
      <div class="kpi-label">Drawdown מקסימלי</div>
      <div class="kpi-value">-{round(max_dd,1)}R</div>
      <div class="kpi-sub">סה"כ {total} עסקאות</div>
    </div>
  </div>

  <div class="charts-grid">
    <div class="chart-card">
      <div class="chart-title"><span class="g"></span>עקומת הון (R)</div>
      <div class="chart-wrap"><canvas id="equityChart"></canvas></div>
    </div>
    <div class="chart-card">
      <div class="chart-title"><span class="b"></span>התפלגות תוצאות</div>
      <div class="chart-wrap"><canvas id="pieChart"></canvas></div>
    </div>
  </div>

  <div class="breakdown-grid">
    <div class="breakdown-card">
      <h3><span></span>לפי סשן</h3>
      {session_cards}
    </div>
    <div class="breakdown-card">
      <h3><span></span>לפי כיוון</h3>
      {direction_cards}
    </div>
  </div>

  <div class="table-card">
    <h3><span></span>יומן עסקאות מלא</h3>
    <table>
      <thead>
        <tr>
          <th>#</th><th>תאריך / שעה</th><th>סשן</th><th>כיוון</th><th>חוזים</th>
          <th>כניסה</th><th>סטופ</th><th>יציאה</th><th>סיכון נק'</th>
          <th>רווח/הפסד נק'</th><th>R</th><th>רווח $</th><th>ציון</th><th>תוצאה</th>
        </tr>
      </thead>
      <tbody>{trade_rows}</tbody>
    </table>
  </div>

  <div class="rules-card">
    <h3><span></span>חוקים שנלמדו מהמסחר</h3>
    <div class="rules-grid">
      <div class="rule"><span class="rule-num">1</span><span class="rule-text">להזיז SL לנקודת כניסה (BE) ברגע שהמחיר מגיע ל-1R רווח — ללא יוצא מן הכלל</span></div>
      <div class="rule"><span class="rule-num">2</span><span class="rule-text">לסגור 35% מהפוזיציה ב-TP1, במיוחד בעסקאות נגד הביאס</span></div>
      <div class="rule"><span class="rule-num">3</span><span class="rule-text">PSP / MES1! Clusters הן אזורי היפוך חזקים — לטפל בהן כיעד TP, לא רק תמיכה/התנגדות</span></div>
      <div class="rule"><span class="rule-num">4</span><span class="rule-text">סטאפים בסשן London איכותיים יותר מסטאפים ב-NY AM</span></div>
      <div class="rule"><span class="rule-num">5</span><span class="rule-text">סגירת נר 5 דקות מתחת לרמת מפתח = סיגנל יציאה</span></div>
      <div class="rule"><span class="rule-num">6</span><span class="rule-text">לא להיכנס בגודל מלא נגד ה-Directional Bias</span></div>
      <div class="rule"><span class="rule-num">7</span><span class="rule-text">כניסה רק כשציון קונפלואנס 7/9 ומעלה — ציון נמוך = גודל פוזיציה קטן יותר</span></div>
      <div class="rule"><span class="rule-num">8</span><span class="rule-text">לבדוק תמיד את שינוי ה-Directional Bias לפני כל עסקה חדשה</span></div>
    </div>
  </div>

</div>

<div class="footer">
  MNQ1! Trading Dashboard &nbsp;|&nbsp; <b>ניתוח Claude AI</b> &nbsp;|&nbsp; {now}
</div>

<script>
const eqCtx = document.getElementById('equityChart').getContext('2d');
const eqData = {equity_points};
new Chart(eqCtx, {{
  type: 'line',
  data: {{
    labels: {eq_labels},
    datasets: [{{
      label: 'Equity (R)',
      data: eqData,
      borderColor: '#4c9be8',
      borderWidth: 2.5,
      pointBackgroundColor: eqData.map((v,i) => i===0?'#4c9be8':(v>=(eqData[i-1]||0)?'#00ff88':'#ff4757')),
      pointRadius: 6,
      pointHoverRadius: 8,
      fill: true,
      backgroundColor: (ctx) => {{
        const g = ctx.chart.ctx.createLinearGradient(0,0,0,210);
        g.addColorStop(0,'rgba(76,155,232,0.2)');
        g.addColorStop(1,'rgba(76,155,232,0.0)');
        return g;
      }},
      tension: 0.4
    }}]
  }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    plugins:{{ legend:{{display:false}}, tooltip:{{ callbacks:{{ label: ctx => ' '+ctx.raw+'R' }} }} }},
    scales:{{
      x:{{ grid:{{color:'rgba(255,255,255,0.04)'}}, ticks:{{color:'#6b7280'}} }},
      y:{{ grid:{{color:'rgba(255,255,255,0.04)'}}, ticks:{{color:'#6b7280', callback: v => v+'R'}} }}
    }}
  }}
}});

const pieCtx = document.getElementById('pieChart').getContext('2d');
new Chart(pieCtx, {{
  type: 'doughnut',
  data: {{
    labels: ['רווח','הפסד','איזון'],
    datasets: [{{
      data: [{len(wins)},{len(losses)},{len(bes)}],
      backgroundColor: ['rgba(0,255,136,0.75)','rgba(255,71,87,0.75)','rgba(255,211,42,0.75)'],
      borderColor: ['#00ff88','#ff4757','#ffd32a'],
      borderWidth: 2, hoverOffset: 8
    }}]
  }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    cutout: '65%',
    plugins:{{
      legend:{{ position:'bottom', labels:{{ color:'#d1d4dc', padding:18, font:{{size:12}} }} }}
    }}
  }}
}});
</script>
</body>
</html>"""

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashbaord updated: {HTML_FILE}")
    webbrowser.open(HTML_FILE)

generate()
