"""
jimmy_tv.py — TradingView reader for Jimmy
מחבר ישירות ל-Chrome CDP port 9222 (אותו מנגנון כמו ה-MCP server)
"""

import json
import base64
import requests
import websocket
from pathlib import Path
from datetime import datetime, timezone, timedelta

CDP_PORT     = 9222
SCREENSHOT_DIR = Path(r"C:\Users\regev\New folder\ninjatrader-mcp\data\screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# JavaScript paths — זהים ל-connection.js של ה-MCP server
CHART_API = "window.TradingViewApi._activeChartWidgetWV.value()"
BARS_PATH = f"{CHART_API}._chartWidget.model().mainSeries().bars()"


def _find_tv_tab() -> str | None:
    """מוצא את הטאב של TradingView ב-Chrome"""
    try:
        resp = requests.get(f"http://localhost:{CDP_PORT}/json/list", timeout=4)
        for t in resp.json():
            if t.get("type") == "page" and "tradingview.com/chart" in t.get("url", ""):
                return t.get("webSocketDebuggerUrl")
        for t in resp.json():
            if t.get("type") == "page" and "tradingview" in t.get("url", "").lower():
                return t.get("webSocketDebuggerUrl")
    except Exception:
        pass
    return None


def _cdp_call(method: str, params: dict = None) -> dict:
    """CDP call → WebSocket → result"""
    ws_url = _find_tv_tab()
    if not ws_url:
        raise Exception("TradingView לא נמצא ב-port 9222 — פתח TradingView Desktop")

    ws = websocket.create_connection(
        ws_url, timeout=15,
        suppress_origin=True
    )
    try:
        # הפעל domains
        for domain_id, domain in [(1, "Runtime"), (2, "Page")]:
            ws.send(json.dumps({"id": domain_id, "method": f"{domain}.enable", "params": {}}))
            ws.recv()

        # בצע את הקריאה
        call_id = 99
        ws.send(json.dumps({"id": call_id, "method": method, "params": params or {}}))
        while True:
            result = json.loads(ws.recv())
            if result.get("id") == call_id:
                if "error" in result:
                    raise Exception(f"CDP error: {result['error']['message']}")
                return result.get("result", {})
    finally:
        try:
            ws.close()
        except Exception:
            pass


def js_eval(expression: str):
    """הרץ JavaScript ב-TradingView tab"""
    result = _cdp_call("Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": False,
    })
    if "exceptionDetails" in result:
        exc = result["exceptionDetails"]
        raise Exception(f"JS error: {exc.get('text','unknown')} | {exc.get('exception',{}).get('description','')}")
    return result.get("result", {}).get("value")


# ──────────────────────────────────────────────
# פונקציות ציבוריות
# ──────────────────────────────────────────────

def health_check() -> bool:
    """בדוק שTradingView פתוח ו-CDP מגיב"""
    try:
        ws_url = _find_tv_tab()
        if not ws_url:
            return False
        result = js_eval("typeof window.TradingViewApi !== 'undefined'")
        return bool(result)
    except Exception:
        return False


def get_quote() -> dict | None:
    """מחיר נוכחי + OHLC מהבר האחרון"""
    try:
        return js_eval(f"""
            (function() {{
                var bars = {BARS_PATH};
                if (!bars || typeof bars.lastIndex !== 'function') return null;
                var i   = bars.lastIndex();
                var v   = bars.valueAt(i);
                if (!v) return null;
                return {{close: v[4], high: v[2], low: v[3], open: v[1], volume: v[5] || 0}};
            }})()
        """)
    except Exception:
        return None


def get_chart_state() -> dict | None:
    """Symbol + timeframe של הגרף הפעיל"""
    try:
        return js_eval(f"""
            (function() {{
                var api = {CHART_API};
                return {{symbol: api.symbol(), timeframe: api.resolution()}};
            }})()
        """)
    except Exception:
        return None


def get_pine_labels(study_filter: str = "") -> list[dict]:
    """
    קרא labels מ-Pine indicators (CDH, CDL, PDH, PDL, TDO, Bias וכו')
    מחזיר: [{"indicator": "Sav FX PDA", "labels": [{"text":"PDH 30763", "price":30763}]}]
    """
    try:
        filter_js = json.dumps(study_filter)
        result = js_eval(f"""
            (function() {{
                var chart   = {CHART_API}._chartWidget;
                var sources = chart.model().model().dataSources();
                var out     = [];
                for (var si = 0; si < sources.length; si++) {{
                    var s = sources[si];
                    if (!s.metaInfo) continue;
                    try {{
                        var meta = s.metaInfo();
                        var name = meta.description || meta.shortDescription || '';
                        if (!name) continue;
                        if ({filter_js} && name.indexOf({filter_js}) === -1) continue;
                        var g = s._graphics;
                        if (!g || !g._primitivesCollection) continue;
                        var pc    = g._primitivesCollection;
                        var items = [];
                        // Labels
                        var dwg = pc.dwglabels;
                        if (dwg) {{
                            var inner = dwg.get('labels');
                            if (inner) {{
                                var coll = inner.get(false);
                                if (coll && coll._primitivesDataById) {{
                                    coll._primitivesDataById.forEach(function(v) {{
                                        var txt   = v.text || v.content || '';
                                        var price = v.price || (v.point && v.point.price) || 0;
                                        if (txt) items.push({{text: txt, price: price}});
                                    }});
                                }}
                            }}
                        }}
                        if (items.length > 0) out.push({{indicator: name, labels: items}});
                    }} catch(e) {{}}
                }}
                return out;
            }})()
        """)
        return result or []
    except Exception:
        return []


def get_pine_lines(study_filter: str = "") -> list[dict]:
    """
    קרא horizontal lines מ-Pine indicators (רמות מחיר)
    מחזיר: [{"indicator": "ICT 5M", "lines": [{"price":30763, "color":"red"}]}]
    """
    try:
        filter_js = json.dumps(study_filter)
        result = js_eval(f"""
            (function() {{
                var chart   = {CHART_API}._chartWidget;
                var sources = chart.model().model().dataSources();
                var out     = [];
                for (var si = 0; si < sources.length; si++) {{
                    var s = sources[si];
                    if (!s.metaInfo) continue;
                    try {{
                        var meta = s.metaInfo();
                        var name = meta.description || meta.shortDescription || '';
                        if (!name) continue;
                        if ({filter_js} && name.indexOf({filter_js}) === -1) continue;
                        var g = s._graphics;
                        if (!g || !g._primitivesCollection) continue;
                        var pc    = g._primitivesCollection;
                        var items = [];
                        var hlines = pc.dwghlines;
                        if (hlines) {{
                            var inner = hlines.get('hlines');
                            if (inner) {{
                                var coll = inner.get(false);
                                if (coll && coll._primitivesDataById) {{
                                    coll._primitivesDataById.forEach(function(v) {{
                                        items.push({{price: v.price || 0}});
                                    }});
                                }}
                            }}
                        }}
                        if (items.length > 0) out.push({{indicator: name, lines: items}});
                    }} catch(e) {{}}
                }}
                return out;
            }})()
        """)
        return result or []
    except Exception:
        return []


def take_screenshot(region: str = "chart") -> tuple[str, str]:
    """
    צלם מסך של TradingView
    region: "chart" | "full"
    מחזיר: (base64_png_string, file_path)
    """
    clip = None

    if region == "chart":
        try:
            bounds = js_eval("""
                (function() {
                    var el = document.querySelector('[data-name="pane-canvas"]')
                          || document.querySelector('[class*="chart-container"]')
                          || document.querySelector('canvas');
                    if (!el) return null;
                    var r = el.getBoundingClientRect();
                    return {x: r.x, y: r.y, width: r.width, height: r.height};
                })()
            """)
            if bounds:
                clip = {
                    "x": bounds["x"], "y": bounds["y"],
                    "width": bounds["width"], "height": bounds["height"],
                    "scale": 1
                }
        except Exception:
            pass

    params = {"format": "png"}
    if clip:
        params["clip"] = clip

    result   = _cdp_call("Page.captureScreenshot", params)
    b64_data = result.get("data", "")

    if not b64_data:
        raise Exception("Screenshot ריק — CDP לא החזיר נתונים")

    ts        = datetime.now().strftime("%H%M%S")
    file_path = str(SCREENSHOT_DIR / f"jimmy_{region}_{ts}.png")
    Path(file_path).write_bytes(base64.b64decode(b64_data))

    return b64_data, file_path


def get_full_tv_context() -> dict:
    """
    קרא את כל הנתונים מ-TradingView בקריאה אחת
    מחזיר dict עם quote + state + labels + lines + screenshot
    """
    ctx = {
        "available": False,
        "quote":     None,
        "state":     None,
        "labels":    [],
        "lines":     [],
        "screenshot_path": None,
        "screenshot_b64":  None,
        "error":     None,
    }

    if not health_check():
        ctx["error"] = "TradingView לא זמין"
        return ctx

    ctx["available"] = True

    try:
        ctx["quote"] = get_quote()
    except Exception as e:
        ctx["error"] = str(e)

    try:
        ctx["state"] = get_chart_state()
    except Exception:
        pass

    try:
        ctx["labels"] = get_pine_labels()
    except Exception:
        pass

    try:
        ctx["lines"] = get_pine_lines()
    except Exception:
        pass

    try:
        b64, path = take_screenshot("chart")
        ctx["screenshot_b64"]  = b64
        ctx["screenshot_path"] = path
    except Exception as e:
        ctx["error"] = f"Screenshot failed: {e}"

    return ctx
