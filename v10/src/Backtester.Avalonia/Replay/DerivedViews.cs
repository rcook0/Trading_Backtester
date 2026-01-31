using System.Globalization;

namespace Backtester.AvaloniaApp.Replay;

public sealed record CandlePoint(DateTime Time, double Open, double High, double Low, double Close, double Volume);
public sealed record EquityPoint(DateTime Time, double Equity);
public sealed record FillPoint(DateTime Time, string Action, string Side, double Price, double Qty, string? Reason);

public sealed record PositionState(string Side, double EntryPrice, double Qty, DateTime EntryTime);

public static class DerivedViews
{
    public static DateTime ParseTime(string iso)
        => DateTime.Parse(iso, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal);

    public static List<CandlePoint> CandlesUpto(EventStream stream)
    {
        var outp = new List<CandlePoint>();
        foreach (var e in stream.Head(true))
        {
            if (e.Type != "BarEvent") continue;
            var p = e.Payload;

            double GetD(string k, double def = 0.0)
                => p.TryGetValue(k, out var v) && v != null && double.TryParse(v.ToString(), out var d) ? d : def;

            outp.Add(new CandlePoint(
                ParseTime(e.Time),
                GetD("open"),
                GetD("high"),
                GetD("low"),
                GetD("close"),
                GetD("volume", 0.0)
            ));
        }
        return outp;
    }

    public static List<EquityPoint> EquityUpto(EventStream stream)
    {
        var outp = new List<EquityPoint>();
        foreach (var e in stream.Head(true))
        {
            if (e.Type != "EquityEvent") continue;
            var p = e.Payload;
            if (!p.TryGetValue("equity", out var v) || v == null) continue;
            if (!double.TryParse(v.ToString(), out var eq)) continue;
            outp.Add(new EquityPoint(ParseTime(e.Time), eq));
        }
        return outp;
    }

    public static List<FillPoint> FillsUpto(EventStream stream)
    {
        var outp = new List<FillPoint>();
        foreach (var e in stream.Head(true))
        {
            if (e.Type != "FillEvent") continue;
            var p = e.Payload;

            string GetS(string k, string def = "")
                => p.TryGetValue(k, out var v) && v != null ? v.ToString()! : def;

            double GetD(string k, double def = 0.0)
                => p.TryGetValue(k, out var v) && v != null && double.TryParse(v.ToString(), out var d) ? d : def;

            outp.Add(new FillPoint(
                ParseTime(e.Time),
                GetS("action"),
                GetS("side"),
                GetD("price"),
                GetD("qty", 0),
                p.TryGetValue("reason", out var rv) ? rv?.ToString() : null
            ));
        }
        return outp;
    }

    public static PositionState? PositionUpto(EventStream stream)
    {
        string side = "FLAT";
        double entry = 0.0;
        double qty = 0.0;
        DateTime entryTime = default;

        foreach (var e in stream.Head(true))
        {
            if (e.Type != "FillEvent") continue;
            var p = e.Payload;

            string action = p.TryGetValue("action", out var av) && av != null ? av.ToString()! : "";
            string s = p.TryGetValue("side", out var sv) && sv != null ? sv.ToString()! : "";
            double price = p.TryGetValue("price", out var pv) && pv != null && double.TryParse(pv.ToString(), out var d) ? d : 0.0;
            double q = p.TryGetValue("qty", out var qv) && qv != null && double.TryParse(qv.ToString(), out var dq) ? dq : 0.0;

            if (action == "OPEN" || action == "REVERSE")
            {
                side = s;
                entry = price;
                qty = q;
                entryTime = ParseTime(e.Time);
            }
            else if (action == "CLOSE")
            {
                side = "FLAT";
                entry = 0.0;
                qty = 0.0;
                entryTime = default;
            }
        }

        return side == "FLAT" ? null : new PositionState(side, entry, qty, entryTime);
    }

    public static double? LastClose(EventStream stream)
    {
        double? last = null;
        foreach (var e in stream.Head(true))
        {
            if (e.Type != "BarEvent") continue;
            if (e.Payload.TryGetValue("close", out var v) && v != null && double.TryParse(v.ToString(), out var d))
                last = d;
        }
        return last;
    }
}
