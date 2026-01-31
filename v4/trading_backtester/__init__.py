"""Trading backtester (Commit 4)

Commit 4 adds a **uniform strategy parameter surface**:

- Every strategy is exposed via `StrategySurface` with:
  - key, name, description
  - a typed parameter schema (ParamSpec list)
  - `.run(df, overrides)` returning signals in a single canonical format

CLI:
- `--describe <strategy>` prints description + param schema
- `--param key=value` overrides any strategy param consistently
"""

from .catalog import list_strategies, get_strategy
from .params import ParamSpec
from .engine import BacktestConfig, backtest
from .data import load_csv_ohlcv
