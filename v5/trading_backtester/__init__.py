"""Trading backtester (Commit 5)

Commit 5 adds **parameter sweeps & optimization** on top of Commit 4's uniform strategy parameter surface.

Exports:
- `sweep`, `SweepConfig` in `trading_backtester.optimize`
- Objective registry in `trading_backtester.objectives`
"""

from .catalog import list_strategies, get_strategy
from .params import ParamSpec
from .engine import BacktestConfig, backtest
from .data import load_csv_ohlcv
from .optimize import sweep, SweepConfig
from .objectives import get_objective
