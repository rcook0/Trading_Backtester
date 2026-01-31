using System;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using Avalonia.Controls;
using Avalonia.Platform.Storage;
using Backtester.AvaloniaApp.Replay;

namespace Backtester.AvaloniaApp;

public sealed class MainWindowViewModel : INotifyPropertyChanged
{
    private readonly EventStream _stream = new();
    private int _cursorIndex;

    public event PropertyChangedEventHandler? PropertyChanged;

    public ObservableCollection<string> EventPreview { get; } = new();

    public ICommand LoadEventsCommand { get; }
    public ICommand StepCommand { get; }
    public ICommand FastForwardCommand { get; }
    public ICommand ToEndCommand { get; }

    public MainWindowViewModel()
    {
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
            CursorIndex = 0;
            RefreshPreview();
        });

        StepCommand = new RelayCommand(_ =>
        {
            _stream.Step(1);
            CursorIndex = _stream.CursorIndex;
            RefreshPreview();
        });

        FastForwardCommand = new RelayCommand(_ =>
        {
            _stream.Step(50);
            CursorIndex = _stream.CursorIndex;
            RefreshPreview();
        });

        ToEndCommand = new RelayCommand(_ =>
        {
            _stream.Seek(_stream.MaxIndex);
            CursorIndex = _stream.CursorIndex;
            RefreshPreview();
        });
    }

    public int CursorIndex
    {
        get => _cursorIndex;
        set
        {
            if (value == _cursorIndex) return;
            _cursorIndex = value;
            _stream.Seek(value);
            OnPropertyChanged();
            OnPropertyChanged(nameof(CursorText));
            OnPropertyChanged(nameof(CurrentTimeText));
            OnPropertyChanged(nameof(EquityText));
            OnPropertyChanged(nameof(PositionText));
            RefreshPreview();
        }
    }

    public int MaxIndex => _stream.MaxIndex;

    public string CursorText => _stream.HasEvents ? $"Cursor: {CursorIndex}/{_stream.MaxIndex}" : "No events loaded";
    public string CurrentTimeText => _stream.CurrentTime != null ? $"Time: {_stream.CurrentTime}" : "Time: —";
    public string EquityText => _stream.LatestEquity() is double eq ? $"Equity: {eq:N2}" : "Equity: —";

    // Placeholder: in Commit 9 we’ll maintain full position state from Fill/TradeClosed events.
    public string PositionText => "Position: (coming next)";

    private void RefreshPreview()
    {
        EventPreview.Clear();
        if (!_stream.HasEvents)
        {
            OnPropertyChanged(nameof(MaxIndex));
            return;
        }

        var head = _stream.Head(true).ToList();
        var tail = head.Count > 25 ? head.Skip(head.Count - 25).ToList() : head;

        foreach (var e in tail)
            EventPreview.Add($"{e.Time}  {e.Type}");

        OnPropertyChanged(nameof(MaxIndex));
        OnPropertyChanged(nameof(CursorText));
        OnPropertyChanged(nameof(CurrentTimeText));
        OnPropertyChanged(nameof(EquityText));
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
