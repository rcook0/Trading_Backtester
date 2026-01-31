using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Markup.Xaml;

namespace Backtester.AvaloniaApp;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        this.AttachedToVisualTree += (_, __) => this.Focus();
    }

    private void InitializeComponent()
    {
        AvaloniaXamlLoader.Load(this);
    }

    private void OnKeyDown(object? sender, KeyEventArgs e)
    {
        if (DataContext is not MainWindowViewModel vm) return;

        if (e.Key == Key.Space)
        {
            vm.TogglePlay();
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Right)
        {
            if (e.KeyModifiers.HasFlag(KeyModifiers.Shift))
                vm.FastForward();
            else
                vm.Step();
            e.Handled = true;
            return;
        }

        if (e.Key == Key.Left)
        {
            vm.StepBack();
            e.Handled = true;
            return;
        }
    }
}
