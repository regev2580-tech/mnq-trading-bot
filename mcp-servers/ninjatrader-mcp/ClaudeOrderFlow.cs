#region Using declarations
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
#endregion

// INSTALLATION:
// 1. Copy this file to: Documents\NinjaTrader 8\bin\Custom\Indicators\
// 2. In NinjaTrader: Tools > Edit NinjaScript > Compile
// 3. Apply to a VOLUMETRIC chart of MNQ1! (5-min recommended)
// 4. Chart must stay open for data to update

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ClaudeOrderFlow : Indicator
    {
        private const string OUTPUT_PATH = @"C:\Users\DELL\New folder\ninjatrader-mcp\data\orderflow.json";
        private const double IMBALANCE_RATIO = 3.0;   // 300% = stacked imbalance
        private const int BARS_TO_EXPORT    = 10;
        private const int CVD_LOOKBACK      = 20;

        private VolumetricBarsType volBars;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name        = "ClaudeOrderFlow";
                Description = "Exports real-time Order Flow data for Claude AI";
                Calculate   = Calculate.OnEachTick;
                IsOverlay   = true;
            }
            else if (State == State.DataLoaded)
            {
                volBars = Bars.BarsSeries.BarsType as VolumetricBarsType;
                if (volBars == null)
                    Print("ClaudeOrderFlow ERROR: Apply to a VOLUMETRIC chart only!");

                string dir = Path.GetDirectoryName(OUTPUT_PATH);
                if (!Directory.Exists(dir))
                    Directory.CreateDirectory(dir);
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 3 || volBars == null) return;
            WriteJson();
        }

        private void WriteJson()
        {
            try
            {
                // ── CVD (cumulative delta, last N bars) ──────────────────────
                double cvd = 0;
                int cvdBars = Math.Min(CVD_LOOKBACK, CurrentBar + 1);
                for (int i = 0; i < cvdBars; i++)
                    cvd += volBars.Volumes[i].GetDelta();

                // ── Bars footprint ───────────────────────────────────────────
                int count = Math.Min(BARS_TO_EXPORT, CurrentBar + 1);
                var sb = new StringBuilder();
                sb.Append("[");

                for (int i = 0; i < count; i++)
                {
                    if (i > 0) sb.Append(",");
                    var vol = volBars.Volumes[i];

                    long delta     = (long)vol.GetDelta();
                    long buyVol    = (long)vol.GetBuyVolume();
                    long sellVol   = (long)vol.GetSellVolume();
                    long totalVol  = (long)vol.GetTotalVolume();
                    long maxDelta  = (long)vol.GetMaxSeenDelta();
                    long minDelta  = (long)vol.GetMinSeenDelta();
                    double poc     = vol.GetPointOfControl();

                    // ── Imbalances ───────────────────────────────────────────
                    var bidImb = new List<double>();
                    var askImb = new List<double>();

                    for (double price = Low[i]; price <= High[i]; price += TickSize)
                    {
                        double buyHere  = vol.GetBuyVolume(price);
                        double sellHere = vol.GetSellVolume(price);
                        double sellBelow = (price - TickSize >= Low[i])
                            ? vol.GetSellVolume(price - TickSize) : 0;
                        double buyAbove  = (price + TickSize <= High[i])
                            ? vol.GetBuyVolume(price + TickSize) : 0;

                        if (sellBelow > 0 && buyHere / sellBelow >= IMBALANCE_RATIO)
                            bidImb.Add(Math.Round(price, 2));
                        if (buyAbove > 0 && sellHere / buyAbove >= IMBALANCE_RATIO)
                            askImb.Add(Math.Round(price, 2));
                    }

                    sb.AppendFormat(
                        "{{\"idx\":{0},\"time\":\"{1}\",\"o\":{2},\"h\":{3},\"l\":{4},\"c\":{5}," +
                        "\"delta\":{6},\"buy_vol\":{7},\"sell_vol\":{8},\"total_vol\":{9}," +
                        "\"max_delta\":{10},\"min_delta\":{11},\"poc\":{12}," +
                        "\"bid_imb\":[{13}],\"ask_imb\":[{14}]}}",
                        i,
                        Time[i].ToString("HH:mm"),
                        Open[i], High[i], Low[i], Close[i],
                        delta, buyVol, sellVol, totalVol,
                        maxDelta, minDelta,
                        Math.Round(poc, 2),
                        string.Join(",", bidImb),
                        string.Join(",", askImb)
                    );
                }
                sb.Append("]");

                // ── Root JSON ────────────────────────────────────────────────
                string json = string.Format(
                    "{{" +
                    "\"symbol\":\"{0}\"," +
                    "\"timeframe\":\"{1}m\"," +
                    "\"timestamp\":\"{2}\"," +
                    "\"price\":{3}," +
                    "\"bid\":{4}," +
                    "\"ask\":{5}," +
                    "\"current_delta\":{6}," +
                    "\"cvd_{7}\":{8}," +
                    "\"bars\":{9}" +
                    "}}",
                    Instrument.MasterInstrument.Name,
                    BarsPeriod.Value,
                    DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss"),
                    Math.Round(Close[0], 2),
                    Math.Round(GetCurrentBid(), 2),
                    Math.Round(GetCurrentAsk(), 2),
                    (long)volBars.Volumes[0].GetDelta(),
                    CVD_LOOKBACK,
                    (long)cvd,
                    sb.ToString()
                );

                File.WriteAllText(OUTPUT_PATH, json, Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Print("ClaudeOrderFlow Error: " + ex.Message);
            }
        }
    }
}
