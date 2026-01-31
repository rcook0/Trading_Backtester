# trading_backtester — Commit 5 (Parameter Sweeps & Optimization)

Commit 4 gave us a **uniform strategy parameter surface**.  
Commit 5 adds a **generic optimizer** that works across every strategy automatically.

## New in Commit 5

- `trading_backtester/optimize.py`
  - grid search and random search
  - returns a ranked pandas DataFrame of results

- `trading_backtester/objectives.py`
  - objective functions for ranking (net %, max DD, profit factor, etc.)

- CLI flags:
  - `--sweep key=a:b:c` numeric inclusive range (e.g. `window=10:100:10`)
  - `--sweep key=v1,v2,v3` discrete set (e.g. `fade_extremes=true,false`)
  - `--sweep key=*` auto-grid from ParamSpec min/max/step (where available)
  - `--sweep-mode grid|random`
  - `--objective <name>`
  - `--out results.csv`

## Examples

List strategies:
```bash
python -m trading_backtester.cli --list
```

Describe a strategy:
```bash
python -m trading_backtester.cli --describe sigma_extreme
```

Grid sweep:
```bash
python -m trading_backtester.cli --csv data.csv --strategy sigma_extreme \
  --sweep window=10:100:10 --sweep sigma=1.5:3.0:0.25 \
  --objective score_balanced --out sweep_sigma.csv
```

Random sweep:
```bash
python -m trading_backtester.cli --csv data.csv --strategy volatility_breakout \
  --sweep-mode random --max-evals 500 --objective net_pct --out sweep_vb.csv
```

Objectives:
```bash
python -m trading_backtester.cli --objectives
```

## Notes

- Execution model is still the Commit 3 engine (single position, SL/TP/trailing).
- Commit 6: walk-forward / OOS validation (the optimizer is designed to support it).
