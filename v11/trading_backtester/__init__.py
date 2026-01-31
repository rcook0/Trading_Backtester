"""Trading backtester (Commit 7)

Commit 7 adds a **formal event stream** to the execution engine.

- `backtest_with_events(...)` returns (trades, equity_curve, events)
- Events are typed dataclasses (Bar/Signal/Fill/Equity/TradeClosed)

This unlocks:
- deterministic step-through playback
- UI integration (Avalonia) without re-implementing backtest logic
- debugging & explainability

"""

from .catalog import list_strategies, get_strategy
from .params import ParamSpec
from .engine import BacktestConfig, backtest, backtest_with_events
from .data import load_csv_ohlcv
from .optimize import sweep, SweepConfig
from .walkforward import walk_forward, WalkForwardConfig
from .objectives import get_objective
from .events import EventBase, BarEvent, SignalEvent, FillEvent, EquityEvent, TradeClosedEvent

from .replay import EventStream, load_events_jsonl, dump_events_jsonl
