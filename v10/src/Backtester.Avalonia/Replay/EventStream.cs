using System.Text.Json;

namespace Backtester.AvaloniaApp.Replay;

public sealed class EventStream
{
    public List<EventRecord> Events { get; } = new();
    public int CursorIndex { get; private set; } = 0;

    public int MaxIndex => Math.Max(0, Events.Count - 1);

    public bool HasEvents => Events.Count > 0;

    public void LoadFromJsonl(string path)
    {
        Events.Clear();
        CursorIndex = 0;

        foreach (var line in File.ReadLines(path))
        {
            var s = line.Trim();
            if (string.IsNullOrWhiteSpace(s)) continue;
            var ev = JsonSerializer.Deserialize<EventRecord>(s);
            if (ev != null) Events.Add(ev);
        }
    }

    public void Seek(int index)
    {
        if (!HasEvents)
        {
            CursorIndex = 0;
            return;
        }
        CursorIndex = Math.Clamp(index, 0, MaxIndex);
    }

    public void Step(int n = 1) => Seek(CursorIndex + n);

    public IEnumerable<EventRecord> Head(bool inclusive = true)
    {
        if (!HasEvents) yield break;
        var end = inclusive ? CursorIndex : Math.Max(0, CursorIndex - 1);
        for (int i = 0; i <= end && i < Events.Count; i++)
            yield return Events[i];
    }

    public string? CurrentTime => HasEvents ? Events[CursorIndex].Time : null;

    public double? LatestEquity()
    {
        double? eq = null;
        foreach (var e in Head(true))
        {
            if (e.Type == "EquityEvent" && e.Payload.TryGetValue("equity", out var v) && v != null)
            {
                if (double.TryParse(v.ToString(), out var d)) eq = d;
            }
        }
        return eq;
    }
}
