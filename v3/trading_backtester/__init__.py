"""Trading backtester (commit 3)

This repo intentionally focuses on **clean interfaces**:
- strategies produce signals/trades from OHLCV data
- engine simulates position management (SL/TP + optional trailing)
- metrics summarize results
"""

from .catalog import list_strategies, get_strategy
from .engine import BacktestConfig, backtest
from .data import load_csv_ohlcv
