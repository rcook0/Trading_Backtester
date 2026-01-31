"""Trading backtester (Commit 6)

Commit 6 adds **walk-forward optimization + out-of-sample (OOS) validation**.

Key idea:
- For each rolling window, optimize params on TRAIN, then evaluate on the subsequent TEST window.
- Records stability diagnostics: parameter drift and performance decay.

Exports:
- `sweep`, `SweepConfig` (Commit 5)
- `walk_forward`, `WalkForwardConfig` (Commit 6)
"""

from .catalog import list_strategies, get_strategy
from .params import ParamSpec
from .engine import BacktestConfig, backtest
from .data import load_csv_ohlcv
from .optimize import sweep, SweepConfig
from .walkforward import walk_forward, WalkForwardConfig
from .objectives import get_objective
