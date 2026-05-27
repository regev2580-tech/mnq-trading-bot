import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import fs from "fs";
import path from "path";

const DATA_FILE = path.resolve("C:/Users/DELL/New folder/ninjatrader-mcp/data/orderflow.json");

function readData() {
  if (!fs.existsSync(DATA_FILE)) {
    throw new Error("orderflow.json not found — is NinjaTrader running with ClaudeOrderFlow indicator active?");
  }
  const raw = fs.readFileSync(DATA_FILE, "utf8").replace(/^﻿/, "");
  const data = JSON.parse(raw);
  const ageMs = Date.now() - new Date(data.timestamp).getTime();
  if (ageMs > 60000) {
    throw new Error(`Data is stale (${Math.round(ageMs/1000)}s old) — is the chart open and live?`);
  }
  return data;
}

function formatBar(bar) {
  const dir = bar.delta >= 0 ? "BULL" : "BEAR";
  const lines = [
    `[${bar.time}] ${dir} | O:${bar.o} H:${bar.h} L:${bar.l} C:${bar.c}`,
    `  Delta: ${bar.delta > 0 ? "+" : ""}${bar.delta} (max:${bar.max_delta} min:${bar.min_delta})`,
    `  Volume: ${bar.total_vol} (Buy:${bar.buy_vol} Sell:${bar.sell_vol})`,
    `  POC: ${bar.poc}`,
  ];
  if (bar.bid_imb.length > 0)
    lines.push(`  BID Imbalances (Selling): ${bar.bid_imb.join(", ")}`);
  if (bar.ask_imb.length > 0)
    lines.push(`  ASK Imbalances (Buying): ${bar.ask_imb.join(", ")}`);
  return lines.join("\n");
}

function detectStackedImbalances(bars) {
  const results = [];
  for (const bar of bars) {
    // Stacked BID imbalances (selling pressure zones)
    if (bar.bid_imb.length >= 3) {
      const sorted = [...bar.bid_imb].sort((a, b) => b - a);
      results.push({
        type: "STACKED_SELLING",
        bar_time: bar.time,
        prices: sorted,
        count: sorted.length,
        note: "Resistance zone — selling imbalances stacked"
      });
    }
    // Stacked ASK imbalances (buying pressure zones)
    if (bar.ask_imb.length >= 3) {
      const sorted = [...bar.ask_imb].sort((a, b) => a - b);
      results.push({
        type: "STACKED_BUYING",
        bar_time: bar.time,
        prices: sorted,
        count: sorted.length,
        note: "Support zone — buying imbalances stacked"
      });
    }
  }
  return results;
}

function detectDivergence(bars) {
  const results = [];
  for (let i = 1; i < bars.length; i++) {
    const curr = bars[i - 1]; // most recent
    const prev = bars[i];

    // Bearish divergence: new high + negative delta + closed lower
    if (curr.h >= prev.h && curr.delta < 0 && curr.c < curr.o) {
      results.push({
        type: "BEARISH_DIVERGENCE",
        time: curr.time,
        price: curr.h,
        delta: curr.delta,
        note: "New high + negative delta + bar closed lower — SHORT signal"
      });
    }

    // Bullish divergence: new low + positive delta + closed higher
    if (curr.l <= prev.l && curr.delta > 0 && curr.c > curr.o) {
      results.push({
        type: "BULLISH_DIVERGENCE",
        time: curr.time,
        price: curr.l,
        delta: curr.delta,
        note: "New low + positive delta + bar closed higher — LONG signal"
      });
    }
  }
  return results;
}

function detectTrapped(bars) {
  const results = [];
  for (const bar of bars) {
    // Trapped sellers: selling imbalance near LOW of bar that closed UP
    const lowZone = bar.l + (bar.h - bar.l) * 0.25;
    const trappedSell = bar.bid_imb.filter(p => p <= lowZone);
    if (trappedSell.length > 0 && bar.c > bar.o) {
      results.push({
        type: "TRAPPED_SELLERS",
        time: bar.time,
        prices: trappedSell,
        note: "Selling imbalance near LOW of up-bar — LONG setup"
      });
    }

    // Trapped buyers: buying imbalance near HIGH of bar that closed DOWN
    const highZone = bar.h - (bar.h - bar.l) * 0.25;
    const trappedBuy = bar.ask_imb.filter(p => p >= highZone);
    if (trappedBuy.length > 0 && bar.c < bar.o) {
      results.push({
        type: "TRAPPED_BUYERS",
        time: bar.time,
        prices: trappedBuy,
        note: "Buying imbalance near HIGH of down-bar — SHORT setup"
      });
    }
  }
  return results;
}

const server = new McpServer({
  name: "ninjatrader-orderflow",
  version: "1.0.0"
});

// ── Tool 1: Full snapshot ────────────────────────────────────────────────────
server.tool(
  "nt_orderflow_snapshot",
  "Full real-time Order Flow snapshot from NinjaTrader 8 — price, delta, CVD, last bars footprint",
  {},
  async () => {
    try {
      const d = readData();
      const cvdKey = Object.keys(d).find(k => k.startsWith("cvd_"));
      const lines = [
        `=== ORDER FLOW SNAPSHOT ===`,
        `Symbol: ${d.symbol} | TF: ${d.timeframe} | Time: ${d.timestamp}`,
        `Price: ${d.price} | Bid: ${d.bid} | Ask: ${d.ask}`,
        `Current Bar Delta: ${d.current_delta > 0 ? "+" : ""}${d.current_delta}`,
        `CVD (${cvdKey} bars): ${d[cvdKey]}`,
        ``,
        `=== HTF LEVELS (Daily) ===`,
        `PDH: ${d.pdh} | PDL: ${d.pdl}`,
        `CDH: ${d.cdh} | CDL: ${d.cdl}`,
        ``,
        `=== LAST ${d.bars.length} BARS ===`,
        ...d.bars.map(formatBar)
      ];
      return { content: [{ type: "text", text: lines.join("\n") }] };
    } catch (e) {
      return { content: [{ type: "text", text: `ERROR: ${e.message}` }] };
    }
  }
);

// ── Tool 2: Delta + CVD only ─────────────────────────────────────────────────
server.tool(
  "nt_delta",
  "Current bar delta and cumulative delta (CVD) — quick bias check",
  {},
  async () => {
    try {
      const d = readData();
      const cvdKey = Object.keys(d).find(k => k.startsWith("cvd_"));
      const cvd = d[cvdKey];
      const bias = cvd > 0 ? "BULLISH" : cvd < 0 ? "BEARISH" : "NEUTRAL";
      const text = [
        `Delta (current bar): ${d.current_delta > 0 ? "+" : ""}${d.current_delta}`,
        `CVD: ${cvd > 0 ? "+" : ""}${cvd} → ${bias}`,
        `Price: ${d.price} @ ${d.timestamp.split("T")[1]}`
      ].join("\n");
      return { content: [{ type: "text", text }] };
    } catch (e) {
      return { content: [{ type: "text", text: `ERROR: ${e.message}` }] };
    }
  }
);

// ── Tool 3: Imbalances ───────────────────────────────────────────────────────
server.tool(
  "nt_imbalances",
  "Stacked bid/ask imbalances across recent bars — support and resistance zones",
  {},
  async () => {
    try {
      const d = readData();
      const stacked = detectStackedImbalances(d.bars);
      if (stacked.length === 0) {
        return { content: [{ type: "text", text: "No stacked imbalances (3+) found in recent bars." }] };
      }
      const lines = stacked.map(s =>
        `[${s.bar_time}] ${s.type} (${s.count} levels)\n  Prices: ${s.prices.join(", ")}\n  → ${s.note}`
      );
      return { content: [{ type: "text", text: lines.join("\n\n") }] };
    } catch (e) {
      return { content: [{ type: "text", text: `ERROR: ${e.message}` }] };
    }
  }
);

// ── Tool 4: Divergence ───────────────────────────────────────────────────────
server.tool(
  "nt_divergence",
  "Detect Orderflows divergence setups (Valtos method): new high/low + opposite delta + bar close confirmation",
  {},
  async () => {
    try {
      const d = readData();
      const divs = detectDivergence(d.bars);
      if (divs.length === 0) {
        return { content: [{ type: "text", text: "No divergence setups detected in recent bars." }] };
      }
      const lines = divs.map(dv =>
        `[${dv.time}] ${dv.type}\n  Price: ${dv.price} | Delta: ${dv.delta}\n  → ${dv.note}`
      );
      return { content: [{ type: "text", text: lines.join("\n\n") }] };
    } catch (e) {
      return { content: [{ type: "text", text: `ERROR: ${e.message}` }] };
    }
  }
);

// ── Tool 5: Trapped traders ──────────────────────────────────────────────────
server.tool(
  "nt_trapped",
  "Detect trapped buyers and sellers (Valtos method) — imbalance near extreme of bar that closed opposite",
  {},
  async () => {
    try {
      const d = readData();
      const trapped = detectTrapped(d.bars);
      if (trapped.length === 0) {
        return { content: [{ type: "text", text: "No trapped buyers/sellers detected in recent bars." }] };
      }
      const lines = trapped.map(t =>
        `[${t.time}] ${t.type}\n  Prices: ${t.prices.join(", ")}\n  → ${t.note}`
      );
      return { content: [{ type: "text", text: lines.join("\n\n") }] };
    } catch (e) {
      return { content: [{ type: "text", text: `ERROR: ${e.message}` }] };
    }
  }
);

// ── Tool 6: Full analysis ────────────────────────────────────────────────────
server.tool(
  "nt_analyze",
  "Full Order Flow analysis — runs all detections and returns trade bias with confidence",
  {},
  async () => {
    try {
      const d = readData();
      const cvdKey = Object.keys(d).find(k => k.startsWith("cvd_"));
      const cvd = d[cvdKey];
      const stacked = detectStackedImbalances(d.bars);
      const divs = detectDivergence(d.bars);
      const trapped = detectTrapped(d.bars);

      const bullish = [];
      const bearish = [];

      if (cvd > 0) bullish.push(`CVD positive (+${cvd})`);
      if (cvd < 0) bearish.push(`CVD negative (${cvd})`);
      if (d.current_delta > 0) bullish.push(`Current bar delta positive (+${d.current_delta})`);
      if (d.current_delta < 0) bearish.push(`Current bar delta negative (${d.current_delta})`);

      stacked.forEach(s => {
        if (s.type === "STACKED_BUYING") bullish.push(`Stacked buying imbalances @ ${s.prices.join(",")}`);
        if (s.type === "STACKED_SELLING") bearish.push(`Stacked selling imbalances @ ${s.prices.join(",")}`);
      });

      divs.forEach(dv => {
        if (dv.type === "BULLISH_DIVERGENCE") bullish.push(`Bullish divergence @ ${dv.price}`);
        if (dv.type === "BEARISH_DIVERGENCE") bearish.push(`Bearish divergence @ ${dv.price}`);
      });

      trapped.forEach(t => {
        if (t.type === "TRAPPED_SELLERS") bullish.push(`Trapped sellers @ ${t.prices.join(",")}`);
        if (t.type === "TRAPPED_BUYERS") bearish.push(`Trapped buyers @ ${t.prices.join(",")}`);
      });

      const score = bullish.length - bearish.length;
      const bias = score > 1 ? "LONG" : score < -1 ? "SHORT" : "NEUTRAL/WAIT";

      const lines = [
        `=== ORDER FLOW ANALYSIS ===`,
        `Symbol: ${d.symbol} | Price: ${d.price} | ${d.timestamp.split("T")[1]}`,
        ``,
        `BIAS: ${bias} (score: ${score > 0 ? "+" : ""}${score})`,
        ``,
        `BULLISH signals (${bullish.length}):`,
        ...bullish.map(b => `  + ${b}`),
        ``,
        `BEARISH signals (${bearish.length}):`,
        ...bearish.map(b => `  - ${b}`),
      ];

      return { content: [{ type: "text", text: lines.join("\n") }] };
    } catch (e) {
      return { content: [{ type: "text", text: `ERROR: ${e.message}` }] };
    }
  }
);

// ── Tool 7: Write trade signal ───────────────────────────────────────────────
const SIGNAL_FILE   = path.resolve("C:/Users/DELL/New folder/ninjatrader-mcp/data/trade_signal.json");
const POSITION_FILE = path.resolve("C:/Users/DELL/New folder/ninjatrader-mcp/data/position.json");

server.tool(
  "nt_signal",
  "Write a trade signal for NinjaTrader to execute. NT8 ClaudeStrategy reads this and places the order automatically.",
  {
    action:    z.enum(["BUY", "SELL"]).describe("Direction: BUY (long) or SELL (short)"),
    price:     z.number().describe("Limit order entry price"),
    sl:        z.number().describe("Stop loss price"),
    tp:        z.number().describe("Take profit price"),
    qty:       z.number().default(1).describe("Number of contracts (default 1)"),
    reason:    z.string().describe("Why this trade — setup description for logging"),
  },
  async ({ action, price, sl, tp, qty, reason }) => {
    try {
      const signal = {
        status:    "pending",
        action,
        price,
        sl,
        tp,
        qty: qty || 1,
        reason,
        timestamp: new Date().toISOString().replace("T", "T").slice(0, 19)
      };
      fs.writeFileSync(SIGNAL_FILE, JSON.stringify(signal), { encoding: "utf8" });

      const rr = action === "BUY"
        ? ((tp - price) / (price - sl)).toFixed(1)
        : ((price - tp) / (sl - price)).toFixed(1);

      const text = [
        `✅ Signal sent to NinjaTrader`,
        `Action: ${action} @ ${price}`,
        `SL: ${sl} | TP: ${tp} | Qty: ${qty || 1}`,
        `R/R: 1:${rr}`,
        `Expires in 30 seconds if not filled`,
        `Reason: ${reason}`
      ].join("\n");

      return { content: [{ type: "text", text }] };
    } catch (e) {
      return { content: [{ type: "text", text: `ERROR writing signal: ${e.message}` }] };
    }
  }
);

// ── Tool 8: Read position status ─────────────────────────────────────────────
server.tool(
  "nt_position",
  "Read current position status from NinjaTrader — entry, SL, TP, unrealized P&L",
  {},
  async () => {
    try {
      if (!fs.existsSync(POSITION_FILE)) {
        return { content: [{ type: "text", text: "position.json not found — is ClaudeStrategy running?" }] };
      }
      const raw = fs.readFileSync(POSITION_FILE, "utf8").replace(/^﻿/, "");
      const p = JSON.parse(raw);

      if (p.status === "flat") {
        return { content: [{ type: "text", text: `Position: FLAT | Price: ${p.price} | ${p.timestamp}` }] };
      }

      const text = [
        `Position: ${p.direction} x${p.qty}`,
        `Entry: ${p.entry} | Current: ${p.price}`,
        `SL: ${p.sl} | TP: ${p.tp}`,
        `Unrealized P&L: ${p.unrealized_pnl > 0 ? "+" : ""}${p.unrealized_pnl} pts`,
        `Time: ${p.timestamp}`
      ].join("\n");

      return { content: [{ type: "text", text }] };
    } catch (e) {
      return { content: [{ type: "text", text: `ERROR: ${e.message}` }] };
    }
  }
);

// ── Start ────────────────────────────────────────────────────────────────────
const transport = new StdioServerTransport();
await server.connect(transport);
