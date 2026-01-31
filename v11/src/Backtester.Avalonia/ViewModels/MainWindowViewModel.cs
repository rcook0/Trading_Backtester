using System;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using Avalonia.Controls;
using Avalonia.Platform.Storage;
using Avalonia.Threading;
using Backtester.AvaloniaApp.Replay;
using OxyPlot;
using OxyPlot.Axes;
using OxyPlot.Series;
using OxyPlot.Annotations;

namespace Backtester.AvaloniaApp;

public sealed class MainWindowViewModel : INotifyPropertyChanged
{
    private readonly EventStream _stream = new();
    private int _cursorIndex;
    private bool _isPlaying;
    private int _speed = 10;
    private readonly DispatcherTimer _timer;

    public event PropertyChangedEventHandler? PropertyChanged;

    public ObservableCollection<string> EventPreview { get; } = new();
    public ObservableCollection<string> TradePreview { get; } = new();

    public ICommand LoadEventsCommand { get; }
    public ICommand TogglePlayCommand { get; }
    public ICommand StepCommand { get; }
    public ICommand FastForwardCommand { get; }
    public ICommand ToEndCommand { get; }

    public PlotModel CandleModel { get; } = new() { Title = "Candles (replay)" };
    public PlotModel EquityModel { get; } = new() { Title = "Equity (replay)" };

    public MainWindowViewModel()
    {
        ConfigureModels();

        _timer = new DispatcherTimer
        {
            Interval = TimeSpan.FromMilliseconds(1000)
        };
        _timer.Tick += (_, __) =>
        {
            if (!_isPlaying) return;
            if (!_stream.HasEvents) return;

            _stream.Step(Speed);
            _cursorIndex = _stream.CursorIndex;
            RefreshAll();

            if (_stream.CursorIndex >= _stream.MaxIndex)
            {
                _isPlaying = false;
                _timer.Stop();
                OnPropertyChanged(nameof(PlayLabel));
                OnPropertyChanged(nameof(PlayingText));
            }
        };

        LoadEventsCommand = new RelayCommand(async _ =>
        {
            var top = TopLevel.GetTopLevel(App.Current?.ApplicationLifetime is Avalonia.Controls.ApplicationLifetimes.IClassicDesktopStyleApplicationLifetime desktop
                ? desktop.MainWindow
                : null);

            if (top == null) return;

            var files = await top.StorageProvider.OpenFilePickerAsync(new FilePickerOpenOptions
            {
                Title = "Select events.jsonl",
                AllowMultiple = false,
                FileTypeFilter = new[] { new FilePickerFileType("JSONL") { Patterns = new[] { "*.jsonl", "*.json" } } }
            });

            if (files.Count == 0) return;

            var path = files[0].TryGetLocalPath();
            if (string.IsNullOrWhiteSpace(path)) return;

            _stream.LoadFromJsonl(path);
            _isPlaying = false;
            _timer.Stop();
            CursorIndex = 0;
            RefreshAll();
        });

        TogglePlayCommand = new RelayCommand(_ => TogglePlay());

        StepCommand = new RelayCommand(_ => { Step(); });
        FastForwardCommand = new RelayCommand(_ => { FastForward(); });
        ToEndCommand = new RelayCommand(_ => { ToEnd(); });
    }

    private void ConfigureModels()
    {
        CandleModel.Axes.Add(new DateTimeAxis
        {
            Position = AxisPosition.Bottom,
            StringFormat = "yyyy-MM-dd\nHH:mm",
            MajorGridlineStyle = LineStyle.Solid,
            MinorGridlineStyle = LineStyle.Dot,
        });
        CandleModel.Axes.Add(new LinearAxis
        {
            Position = AxisPosition.Left,
            MajorGridlineStyle = LineStyle.Solid,
            MinorGridlineStyle = LineStyle.Dot,
            IsZoomEnabled = true,
            IsPanEnabled = true
        });

        EquityModel.Axes.Add(new DateTimeAxis
        {
            Position = AxisPosition.Bottom,
            StringFormat = "yyyy-MM-dd\nHH:mm",
            MajorGridlineStyle = LineStyle.Solid,
            MinorGridlineStyle = LineStyle.Dot,
        });
        EquityModel.Axes.Add(new LinearAxis
        {
            Position = AxisPosition.Left,
            MajorGridlineStyle = LineStyle.Solid,
            MinorGridlineStyle = LineStyle.Dot,
        });
    }

    public int Speed
    {
        get => _speed;
        set
        {
            if (value == _speed) return;
            _speed = Math.Clamp(value, 1, 30);
            OnPropertyChanged();
            OnPropertyChanged(nameof(SpeedText));
        }
    }

    public string SpeedText => $"{Speed} bars/sec";

    public string PlayLabel => _isPlaying ? "Pause" : "Play";
    public string PlayingText => _isPlaying ? "▶ Playing" : "⏸ Paused";

    public int CursorIndex
    {
        get => _cursorIndex;
        set
        {
            if (value == _cursorIndex) return;
            _cursorIndex = value;
            _stream.Seek(value);
            OnPropertyChanged();
            RefreshAll();
        }
    }

    public int MaxIndex => _stream.MaxIndex;

    public string CursorText => _stream.HasEvents ? $"Cursor: {CursorIndex}/{_stream.MaxIndex}" : "No events loaded";
    public string CurrentTimeText => _stream.CurrentTime != null ? $"Time: {_stream.CurrentTime}" : "Time: —";
    public string EquityText => _stream.LatestEquity() is double eq ? $"Equity: {eq:N2}" : "Equity: —";

    public string PositionText
    {
        get
        {
            var pos = DerivedViews.PositionUpto(_stream);
            return pos == null ? "Position: FLAT" : $"Position: {pos.Side} qty={pos.Qty:N2} entry={pos.EntryPrice:N2}";
        }
    }

    public string UnrealizedText
    {
        get
        {
            var pos = DerivedViews.PositionUpto(_stream);
            var last = DerivedViews.LastClose(_stream);
            if (pos == null || last == null) return "Unrealized: —";

            var dir = pos.Side == "BUY" ? 1.0 : -1.0;
            var pnl = (last.Value - pos.EntryPrice) * dir * pos.Qty;
            var pct = pos.EntryPrice != 0 ? (last.Value / pos.EntryPrice - 1.0) * dir : 0.0;
            return $"Unrealized: {pnl:N2} ({pct*100:N2}%) @ last={last.Value:N2}";
        }
    }

    // -------- methods called from code-behind for keyboard control --------
    public void TogglePlay()
    {
        if (!_stream.HasEvents) return;

        _isPlaying = !_isPlaying;
        OnPropertyChanged(nameof(PlayLabel));
        OnPropertyChanged(nameof(PlayingText));

        if (_isPlaying)
            _timer.Start();
        else
            _timer.Stop();
    }

    public void Step()
    {
        if (!_stream.HasEvents) return;
        _isPlaying = false;
        _timer.Stop();
        _stream.Step(1);
        _cursorIndex = _stream.CursorIndex;
        RefreshAll();
        OnPropertyChanged(nameof(PlayLabel));
        OnPropertyChanged(nameof(PlayingText));
    }

    public void StepBack()
    {
        if (!_stream.HasEvents) return;
        _isPlaying = false;
        _timer.Stop();
        _stream.Seek(Math.Max(0, _stream.CursorIndex - 1));
        _cursorIndex = _stream.CursorIndex;
        RefreshAll();
        OnPropertyChanged(nameof(PlayLabel));
        OnPropertyChanged(nameof(PlayingText));
    }

    public void FastForward()
    {
        if (!_stream.HasEvents) return;
        _isPlaying = false;
        _timer.Stop();
        _stream.Step(50);
        _cursorIndex = _stream.CursorIndex;
        RefreshAll();
        OnPropertyChanged(nameof(PlayLabel));
        OnPropertyChanged(nameof(PlayingText));
    }

    public void ToEnd()
    {
        if (!_stream.HasEvents) return;
        _isPlaying = false;
        _timer.Stop();
        _stream.Seek(_stream.MaxIndex);
        _cursorIndex = _stream.CursorIndex;
        RefreshAll();
        OnPropertyChanged(nameof(PlayLabel));
        OnPropertyChanged(nameof(PlayingText));
    }

    private void RefreshAll()
    {
        RefreshPreview();
        RefreshTrades();
        RefreshCharts();

        OnPropertyChanged(nameof(MaxIndex));
        OnPropertyChanged(nameof(CursorText));
        OnPropertyChanged(nameof(CurrentTimeText));
        OnPropertyChanged(nameof(EquityText));
        OnPropertyChanged(nameof(PositionText));
        OnPropertyChanged(nameof(UnrealizedText));
        OnPropertyChanged(nameof(PlayingText));
    }

    private void RefreshPreview()
    {
        EventPreview.Clear();
        if (!_stream.HasEvents) return;

        var head = _stream.Head(true).ToList();
        var tail = head.Count > 25 ? head.Skip(head.Count - 25).ToList() : head;

        foreach (var e in tail)
            EventPreview.Add($"{e.Time}  {e.Type}");
    }

    private void RefreshTrades()
    {
        TradePreview.Clear();
        if (!_stream.HasEvents) return;

        var trades = TradeViews.TradeClosesUpto(_stream);
        var tail = trades.Count > 25 ? trades.Skip(trades.Count - 25).ToList() : trades;

        foreach (var t in tail)
        {
            TradePreview.Add($"{t.Time:yyyy-MM-dd HH:mm}  {t.Side}  pnl={t.PnL:N2} ({t.PnLPct*100:N2}%)");
        }
    }

    private void RefreshCharts()
    {
        CandleModel.Series.Clear();
        CandleModel.Annotations.Clear();
        EquityModel.Series.Clear();

        if (!_stream.HasEvents)
        {
            CandleModel.InvalidatePlot(true);
            EquityModel.InvalidatePlot(true);
            return;
        }

        var candles = DerivedViews.CandlesUpto(_stream);
        var fills = DerivedViews.FillsUpto(_stream);
        var eq = DerivedViews.EquityUpto(_stream);
        var pos = DerivedViews.PositionUpto(_stream);

        // Candles
        var cs = new CandleStickSeries
        {
            IncreasingFill = OxyColors.Transparent,
            DecreasingFill = OxyColors.Transparent,
        };

        foreach (var c in candles)
        {
            cs.Append(new HighLowItem(DateTimeAxis.ToDouble(c.Time), c.High, c.Low, c.Open, c.Close));
        }
        CandleModel.Series.Add(cs);

        // Fill markers
        if (fills.Count > 0)
        {
            var buyMarkers = new ScatterSeries { MarkerType = MarkerType.Triangle, MarkerSize = 4 };
            var sellMarkers = new ScatterSeries { MarkerType = MarkerType.Triangle, MarkerSize = 4 };

            foreach (var f in fills)
            {
                var x = DateTimeAxis.ToDouble(f.Time);
                var pt = new ScatterPoint(x, f.Price);
                if (f.Side == "BUY") buyMarkers.Points.Add(pt);
                else if (f.Side == "SELL") sellMarkers.Points.Add(pt);
            }

            if (buyMarkers.Points.Count > 0) CandleModel.Series.Add(buyMarkers);
            if (sellMarkers.Points.Count > 0) CandleModel.Series.Add(sellMarkers);
        }

        // Active entry line (foundation for SL/TP lines via future events)
        if (pos != null)
        {
            CandleModel.Annotations.Add(new LineAnnotation
            {
                Type = LineAnnotationType.Horizontal,
                Y = pos.EntryPrice,
                LineStyle = LineStyle.Dot
            });
        }

        // Equity
        var line = new LineSeries();
        foreach (var p in eq)
        {
            line.Points.Add(new DataPoint(DateTimeAxis.ToDouble(p.Time), p.Equity));
        }
        EquityModel.Series.Add(line);

        CandleModel.InvalidatePlot(true);
        EquityModel.InvalidatePlot(true);
    }

    private void OnPropertyChanged([CallerMemberName] string? name = null)
        => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
}

internal sealed class RelayCommand : ICommand
{
    private readonly Func<object?, System.Threading.Tasks.Task>? _async;
    private readonly Action<object?>? _sync;

    public RelayCommand(Action<object?> execute) => _sync = execute;
    public RelayCommand(Func<object?, System.Threading.Tasks.Task> executeAsync) => _async = executeAsync;

    public event EventHandler? CanExecuteChanged;
    public bool CanExecute(object? parameter) => true;

    public async void Execute(object? parameter)
    {
        if (_sync != null) _sync(parameter);
        if (_async != null) await _async(parameter);
    }
}
