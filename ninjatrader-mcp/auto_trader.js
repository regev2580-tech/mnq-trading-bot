import fs from "fs";
import path from "path";

const DATA_FILE     = path.resolve("C:/Users/DELL/New folder/ninjatrader-mcp/data/orderflow.json");
const SIGNAL_FILE   = path.resolve("C:/Users/DELL/New folder/ninjatrader-mcp/data/trade_signal.json");
const POSITION_FILE = path.resolve("C:/Users/DELL/New folder/ninjatrader-mcp/data/position.json");
const LOG_FILE      = path.resolve("C:/Users/DELL/New folder/ninjatrader-mcp/data/auto_log.txt");
const STATE_FILE    = path.resolve("C:/Users/DELL/New folder/ninjatrader-mcp/data/auto_state.json");

// Kill Zone: 16:30-18:00 Israel (UTC+3) = 13:30-15:00 UTC
const KZ_START_MIN = 13 * 60 + 30;
const KZ_END_MIN   = 15 * 60 + 0;

const MAX_DAILY_TRADES = 2;
const MIN_SCORE        = 3;   // minimum signal score out of possible ~7
const MIN_RR           = 2.0; // minimum risk/reward ratio
const CHECK_INTERVAL   = 30 * 1000; // 30 seconds
const DATA_MAX_AGE_MS  = 60 * 1000; // reject stale data older than 60s
const SIGNAL_COOLDOWN  = 5 * 60 * 1000; // 5 min cooldown between signals

// Test mode: bypasses Kill Zone hours check (for Market Replay / paper testing)
const TEST_MODE = process.argv.includes("--test");

function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}`;
  console.log(line);
  fs.appendFileSync(LOG_FILE, line + "\n", { encoding: "utf8" });
}

function isKillZone() {
  const now = new Date();
  const utcMin = now.getUTCHours() * 60 + now.getUTCMinutes();
  return utcMin >= KZ_START_MIN && utcMin < KZ_END_MIN;
}

function loadState() {
  const today = new Date().toISOString().slice(0, 10);
  try {
    if (fs.existsSync(STATE_FILE)) {
      const s = JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
      if (s.date === today) return s;
    }
  } catch (_) {}
  return { date: today, trades: 0, lastSignalTime: 0 };
}

function saveState(state) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state), { encoding: "utf8" });
}

function readData() {
  if (!fs.existsSync(DATA_FILE)) throw new Error("orderflow.json not found — NT8 running?");
  const raw = fs.readFileSync(DATA_FILE, "utf8").replace(/^﻿/, "");
  const data = JSON.parse(raw);
  const ageMs = Date.now() - new Date(data.timestamp).getTime();
  if (ageMs > DATA_MAX_AGE_MS) throw new Error(`Stale data: ${Math.round(ageMs / 1000)}s old`);
  return data;
}

function readPosition() {
  try {
    if (!fs.existsSync(POSITION_FILE)) return { status: "flat" };
    return JSON.parse(fs.readFileSync(POSITION_FILE, "utf8").replace(/^﻿/, ""));
  } catch (_) { return { status: "flat" }; }
}

function readSignal() {
  try {
    if (!fs.existsSync(SIGNAL_FILE)) return null;
    return JSON.parse(fs.readFileSync(SIGNAL_FILE, "utf8").replace(/^﻿/, ""));
  } catch (_) { return null; }
}

// ── Setup detection (Valtos Order Flow method) ────────────────────────────────

function detectSetup(data) {
  const bars = data.bars || [];
  const cvdKey = Object.keys(data).find(k => k.startsWith("cvd_"));
  const cvd = cvdKey ? (data[cvdKey] || 0) : 0;

  let bullScore = 0;
  let bearScore = 0;
  const bullReasons = [];
  const bearReasons = [];

  // 1. CVD bias (momentum filter)
  if (cvd > 500)  { bullScore++; bullReasons.push(`CVD +${cvd}`); }
  if (cvd < -500) { bearScore++; bearReasons.push(`CVD ${cvd}`); }

  // 2. Current bar delta
  if (data.current_delta > 0) { bullScore++; bullReasons.push(`Delta +${data.current_delta}`); }
  if (data.current_delta < 0) { bearScore++; bearReasons.push(`Delta ${data.current_delta}`); }

  // 3. Stacked imbalances (3+ in one bar)
  for (const bar of bars) {
    if (bar.ask_imb && bar.ask_imb.length >= 3) {
      bullScore++;
      const lo = Math.min(...bar.ask_imb);
      const hi = Math.max(...bar.ask_imb);
      bullReasons.push(`Stacked ASK imb [${bar.ask_imb.length}] @ ${lo}-${hi}`);
    }
    if (bar.bid_imb && bar.bid_imb.length >= 3) {
      bearScore++;
      const lo = Math.min(...bar.bid_imb);
      const hi = Math.max(...bar.bid_imb);
      bearReasons.push(`Stacked BID imb [${bar.bid_imb.length}] @ ${lo}-${hi}`);
    }
  }

  // 4. Delta divergence
  for (let i = 1; i < bars.length; i++) {
    const curr = bars[i - 1];
    const prev = bars[i];
    if (curr.l <= prev.l && curr.delta > 0 && curr.c > curr.o) {
      bullScore++;
      bullReasons.push(`Bullish divergence @ ${curr.l} (new low + pos delta + closed up)`);
    }
    if (curr.h >= prev.h && curr.delta < 0 && curr.c < curr.o) {
      bearScore++;
      bearReasons.push(`Bearish divergence @ ${curr.h} (new high + neg delta + closed down)`);
    }
  }

  // 5. Trapped traders
  for (const bar of bars) {
    if (!bar.bid_imb || !bar.ask_imb) continue;
    const range = bar.h - bar.l;
    if (range === 0) continue;
    const lowZone  = bar.l + range * 0.25;
    const highZone = bar.h - range * 0.25;
    const trappedSell = bar.bid_imb.filter(p => p <= lowZone);
    if (trappedSell.length > 0 && bar.c > bar.o) {
      bullScore++;
      bullReasons.push(`Trapped sellers @ ${trappedSell.join(",")}`);
    }
    const trappedBuy = bar.ask_imb.filter(p => p >= highZone);
    if (trappedBuy.length > 0 && bar.c < bar.o) {
      bearScore++;
      bearReasons.push(`Trapped buyers @ ${trappedBuy.join(",")}`);
    }
  }

  const netScore = bullScore - bearScore;
  const bias = netScore >= MIN_SCORE ? "LONG" : netScore <= -MIN_SCORE ? "SHORT" : "NEUTRAL";

  return { bullScore, bearScore, netScore, bullReasons, bearReasons, bias, cvd };
}

// ── Signal price calculation ──────────────────────────────────────────────────

function buildSignal(data, bias) {
  const price = data.price;
  const bars  = data.bars || [];

  if (bias === "LONG") {
    const entry = price;
    // SL: below lowest BID imbalance below price, or recent bar low
    const allBidImb = bars.flatMap(b => b.bid_imb || []).filter(p => p < price);
    const recentLow  = bars.length > 0 ? Math.min(...bars.slice(0, 3).map(b => b.l)) : price - 20;
    const slBase     = allBidImb.length > 0 ? Math.min(...allBidImb) : recentLow;
    const sl         = Math.round((slBase - 0.5) * 4) / 4;
    // TP: nearest HTF level above price with enough room for R/R
    const riskPts    = entry - sl;
    const minTarget  = entry + riskPts * MIN_RR;
    const targets    = [data.cdh, data.pdh].filter(t => t && t >= minTarget);
    const tp         = targets.length > 0
      ? Math.round(Math.min(...targets) * 4) / 4
      : Math.round((entry + riskPts * MIN_RR) * 4) / 4;
    const rr         = (tp - entry) / riskPts;
    return { entry: Math.round(entry * 4) / 4, sl, tp, rr };
  } else {
    const entry = price;
    const allAskImb  = bars.flatMap(b => b.ask_imb || []).filter(p => p > price);
    const recentHigh = bars.length > 0 ? Math.max(...bars.slice(0, 3).map(b => b.h)) : price + 20;
    const slBase     = allAskImb.length > 0 ? Math.max(...allAskImb) : recentHigh;
    const sl         = Math.round((slBase + 0.5) * 4) / 4;
    const riskPts    = sl - entry;
    const minTarget  = entry - riskPts * MIN_RR;
    const targets    = [data.cdl, data.pdl].filter(t => t && t <= minTarget);
    const tp         = targets.length > 0
      ? Math.round(Math.max(...targets) * 4) / 4
      : Math.round((entry - riskPts * MIN_RR) * 4) / 4;
    const rr         = (entry - tp) / riskPts;
    return { entry: Math.round(entry * 4) / 4, sl, tp, rr };
  }
}

function writeSignal(action, sig, reasons) {
  const payload = {
    status:    "pending",
    action,
    price:     sig.entry,
    sl:        sig.sl,
    tp:        sig.tp,
    qty:       1,
    reason:    reasons.slice(0, 3).join(" | "),
    timestamp: new Date().toISOString().replace("T", "T").slice(0, 19)
  };
  fs.writeFileSync(SIGNAL_FILE, JSON.stringify(payload), { encoding: "utf8" });
  return payload.timestamp;
}

// ── Main tick ─────────────────────────────────────────────────────────────────

async function tick() {
  try {
    if (!TEST_MODE && !isKillZone()) {
      const now = new Date();
      const utcMin = now.getUTCHours() * 60 + now.getUTCMinutes();
      const minsToKZ = KZ_START_MIN - utcMin;
      if (minsToKZ > 0 && minsToKZ < 120) {
        log(`Outside Kill Zone — ${minsToKZ} min to start`);
      }
      return;
    }

    const state = loadState();

    if (state.trades >= MAX_DAILY_TRADES) {
      log(`Daily limit reached (${state.trades}/${MAX_DAILY_TRADES}) — done for today`);
      return;
    }

    // If in position — just report, don't trade
    const pos = readPosition();
    if (pos.status === "open") {
      log(`IN POSITION: ${pos.direction} x${pos.qty} | entry:${pos.entry} | uPnL:${pos.unrealized_pnl > 0 ? "+" : ""}${pos.unrealized_pnl} pts`);
      return;
    }

    // If signal pending — wait for NT8
    const sig = readSignal();
    if (sig && sig.status === "pending") {
      log(`Signal pending @ ${sig.price} — waiting for NT8`);
      return;
    }

    // Cooldown between signals
    if (Date.now() - state.lastSignalTime < SIGNAL_COOLDOWN) {
      const secLeft = Math.round((SIGNAL_COOLDOWN - (Date.now() - state.lastSignalTime)) / 1000);
      log(`Cooldown: ${secLeft}s remaining`);
      return;
    }

    // Read live order flow
    const data = readData();

    // Detect setup
    const setup = detectSetup(data);
    const scoreStr = `${setup.netScore > 0 ? "+" : ""}${setup.netScore}`;
    log(`SCAN | Price:${data.price} | Score:${scoreStr} | CVD:${setup.cvd > 0 ? "+" : ""}${setup.cvd} | Bias:${setup.bias}`);

    if (setup.bias === "NEUTRAL") return;

    const action  = setup.bias === "LONG" ? "BUY" : "SELL";
    const reasons = setup.bias === "LONG" ? setup.bullReasons : setup.bearReasons;
    const signal  = buildSignal(data, setup.bias);

    if (signal.rr < MIN_RR) {
      log(`R/R too low: 1:${signal.rr.toFixed(1)} (min 1:${MIN_RR}) — skip`);
      return;
    }

    // Send signal
    writeSignal(action, signal, reasons);
    state.trades++;
    state.lastSignalTime = Date.now();
    saveState(state);

    log(`>>> SIGNAL: ${action} @ ${signal.entry} | SL:${signal.sl} | TP:${signal.tp} | R/R:1:${signal.rr.toFixed(1)}`);
    log(`    Setup: ${reasons.join(" | ")}`);

  } catch (e) {
    log(`ERR: ${e.message}`);
  }
}

// ── Start ─────────────────────────────────────────────────────────────────────

const kzStartStr = `${(KZ_START_MIN/60|0).toString().padStart(2,"0")}:${String(KZ_START_MIN%60).padStart(2,"0")} UTC`;
const kzEndStr   = `${(KZ_END_MIN/60|0).toString().padStart(2,"0")}:${String(KZ_END_MIN%60).padStart(2,"0")} UTC`;

log("=================================================");
log("  AUTO TRADER started (Sim101 / paper trading)");
log(`  Kill Zone: ${kzStartStr} - ${kzEndStr} (16:30-18:00 Israel)${TEST_MODE ? " [TEST MODE - bypassed]" : ""}`);
log(`  Max trades/day: ${MAX_DAILY_TRADES} | Min score: ${MIN_SCORE}/7 | Min R/R: 1:${MIN_RR}`);
log(`  Check interval: ${CHECK_INTERVAL/1000}s`);
log("=================================================");

tick();
setInterval(tick, CHECK_INTERVAL);
