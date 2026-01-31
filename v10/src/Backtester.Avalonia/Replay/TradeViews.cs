using System.Globalization;

namespace Backtester.AvaloniaApp.Replay;

public sealed record TradeClosePoint(DateTime Time, string Side, double EntryPrice, double ExitPrice, double PnL, double PnLPct, string? Reason);

public static class TradeViews
{
    private static DateTime ParseTime(string iso)
        => DateTime.Parse(iso, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal);

    private static double GetD(Dictionary<string, object?> p, string k, double def = 0.0)
        => p.TryGetValue(k, out var v) && v != null && double.TryParse(v.ToString(), out var d) ? d : def;

    private static string GetS(Dictionary<string, object?> p, string k, string def = "")
        => p.TryGetValue(k, out var v) && v != null ? v.ToString()! : def;

    public static List<TradeClosePoint> TradeClosesUpto(EventStream stream)
    {
        var outp = new List<TradeClosePoint>();
        foreach (var e in stream.Head(true))
        {
            if (e.Type != "TradeClosedEvent") continue;
            var p = e.Payload;
            outp.Add(new TradeClosePoint(
                ParseTime(e.Time),
                GetS(p, "side"),
                GetD(p, "entry_price"),
                GetD(p, "exit_price"),
                GetD(p, "pnl"),
                GetD(p, "pnl_pct"),
                p.TryGetValue("reason", out var rv) ? rv?.ToString() : null
            ));
        }
        return outp;
    }
}
