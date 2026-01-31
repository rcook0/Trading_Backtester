# trading_backtester — Commit 4 (Uniform Strategy Parameters)

Commit 2: 16 strategies  
Commit 3: CSV loader + engine + metrics + CLI  
**Commit 4: uniform parameter surface across all strategies** ✅

## What “uniform” means here

Every strategy is represented by a `StrategySurface` with:
- `key`, `name`, `description`
- `params`: typed schema (`ParamSpec` list with defaults + ranges)
- `run(df, overrides)` → signals in canonical format: `(time, BUY/SELL, price)`

No more “each strategy has its own init signature and magic defaults” at the UI/CLI level.

## CLI

List strategies:
```bash
python -m trading_backtester.cli --list
```

Describe a strategy (including its parameters):
```bash
python -m trading_backtester.cli --describe sigma_extreme
```

Run with param overrides:
```bash
python -m trading_backtester.cli --csv data.csv --strategy sigma_extreme --param window=50 --param sigma=2.5
python -m trading_backtester.cli --csv data.csv --strategy volatility_breakout --param lookback=40 --param k=0.7
```

## CSV format (normalized)

Headers (case-insensitive):
```csv
time,open,high,low,close,volume
```

Volume is optional.

## Next upgrades (Commit 5+)

- Standardize *holding period / exit rules per strategy* (some are “signal-only”, exits are engine SL/TP).
- Walk-forward / OOS evaluation + parameter sweeps.
- Add a lightweight UI (Streamlit or Avalonia) that auto-renders ParamSpec inputs.
