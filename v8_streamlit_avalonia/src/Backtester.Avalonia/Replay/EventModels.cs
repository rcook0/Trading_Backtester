using System.Text.Json.Serialization;

namespace Backtester.AvaloniaApp.Replay;

// Minimal mirror of the Commit 7 JSONL contract.
public sealed class EventRecord
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("time")]
    public string Time { get; set; } = "";

    [JsonPropertyName("payload")]
    public Dictionary<string, object?> Payload { get; set; } = new();
}
