const fs   = require('fs');
const path = require('path');

const DATA_FILE = path.join(__dirname, '../data/orderflow.json');

function readData() {
  try {
    const raw = fs.readFileSync(DATA_FILE, 'utf8');
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

function isStale(data, maxAgeSeconds = 10) {
  if (!data || !data.timestamp) return true;
  const ts  = new Date(data.timestamp);
  const age = (Date.now() - ts.getTime()) / 1000;
  return age > maxAgeSeconds;
}

// ── Commands ────────────────────────────────────────────────────────────────

function cmdOrderflow() {
  const d = readData();
  if (!d) return { success: false, error: 'No data. Is NinjaTrader running with ClaudeOrderFlow indicator on a Volumetric chart?' };
  if (isStale(d)) return { success: false, error: `Data is stale (last update: ${d.timestamp}). Check NinjaTrader.` };
  return { success: true, ...d };
}

function cmdDelta() {
  const d = readData();
  if (!d) return { success: false, error: 'No data from NinjaTrader.' };
  if (isStale(d)) return { success: false, error: 'Stale data.' };

  const bar = d.bars[0];
  return {
    success:       true,
    symbol:        d.symbol,
    timestamp:     d.timestamp,
    price:         d.price,
    current_delta: d.current_delta,
    cvd:           d[`cvd_${Object.keys(d).find(k => k.startsWith('cvd_'))?.split('_')[1] || 20}`] || 0,
    bar_delta:     bar?.delta,
    buy_vol:       bar?.buy_vol,
    sell_vol:      bar?.sell_vol,
    total_vol:     bar?.total_vol,
    max_delta:     bar?.max_delta,
    min_delta:     bar?.min_delta,
    poc:           bar?.poc
  };
}

function cmdImbalances() {
  const d = readData();
  if (!d) return { success: false, error: 'No data from NinjaTrader.' };
  if (isStale(d)) return { success: false, error: 'Stale data.' };

  const result = [];
  for (const bar of d.bars) {
    if ((bar.bid_imb && bar.bid_imb.length > 0) || (bar.ask_imb && bar.ask_imb.length > 0)) {
      result.push({
        time:    bar.time,
        high:    bar.h,
        low:     bar.l,
        close:   bar.c,
        delta:   bar.delta,
        bid_imbalances: bar.bid_imb,
        ask_imbalances: bar.ask_imb
      });
    }
  }

  return {
    success:    true,
    symbol:     d.symbol,
    timestamp:  d.timestamp,
    price:      d.price,
    bars_with_imbalances: result
  };
}

function cmdFootprint(n = 5) {
  const d = readData();
  if (!d) return { success: false, error: 'No data from NinjaTrader.' };
  if (isStale(d)) return { success: false, error: 'Stale data.' };

  const bars = d.bars.slice(0, Math.min(n, d.bars.length));
  return {
    success:   true,
    symbol:    d.symbol,
    timeframe: d.timeframe,
    timestamp: d.timestamp,
    price:     d.price,
    bars
  };
}

// ── CLI entry point ─────────────────────────────────────────────────────────

const [,, cmd, ...args] = process.argv;

const commands = {
  orderflow:  () => cmdOrderflow(),
  delta:      () => cmdDelta(),
  imbalances: () => cmdImbalances(),
  footprint:  () => cmdFootprint(parseInt(args[0]) || 5),
};

if (!cmd || !commands[cmd]) {
  const available = Object.keys(commands).join(', ');
  console.log(JSON.stringify({ success: false, error: `Unknown command. Available: ${available}` }));
  process.exit(1);
}

console.log(JSON.stringify(commands[cmd](), null, 2));
