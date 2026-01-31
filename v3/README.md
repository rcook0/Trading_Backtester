# trading_backtester — Commit 3

Commit 2 was “16 strategies”. Commit 3 turns that into a **usable backtesting package** with:

- A **strategy catalog** (keys, names, descriptions)
- A **CSV loader** for OHLCV data
- A simple **single-position engine** with SL/TP + optional trailing stop
- Basic performance **metrics** (net %, max drawdown, profit factor)

## Install / run (from repo root)

```bash
python -m trading_backtester.cli --list
python -m trading_backtester.cli --csv path/to/data.csv --strategy sigma_extreme
```

## CSV format

Headers (case-insensitive) expected:

```csv
time,open,high,low,close,volume
```

`volume` is optional.

## Next (Commit 4 ideas)

- Parameter system: surface per-strategy params consistently via CLI and UI
- Multi-position / pyramiding, commissions, spread/slippage models
- Walk-forward evaluation + in-sample/out-of-sample splits
- Portfolio mode (multiple symbols) + correlation-aware sizing
