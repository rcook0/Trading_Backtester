# trading_backtester — Commit 6 (Walk-forward + OOS Validation)

Commit 4: uniform strategy parameter surface  
Commit 5: parameter sweeps & optimization  
**Commit 6: walk-forward optimization + out-of-sample evaluation** ✅

## What Commit 6 does

For each rolling window:
1) Take a TRAIN segment (e.g. 180 days)
2) Optimize parameters on TRAIN (grid or random sweep)
3) Apply best parameters to the following TEST segment (e.g. 30 days)
4) Record both TRAIN and TEST metrics

Additionally records stability signals:
- `param_drift`: how much best params changed vs prior window
- `performance_decay`: test_net_pct / train_net_pct (rough sanity check)

Outputs:
- `windows_df`: one row per window (train/test bounds, metrics, best params JSON)
- `oos_equity_df`: concatenated OOS equity curves (window_id, time, equity)

## CLI Examples

### Walk-forward run
```bash
python -m trading_backtester.cli --csv data.csv --strategy sigma_extreme \
  --walk-forward \
  --train-days 180 --test-days 30 --step-days 30 \
  --sweep window=10:120:10 --sweep sigma=1.5:3.0:0.25 \
  --objective score_balanced --sweep-mode grid --cap-grid --max-evals 800 \
  --out wf_windows.csv --out-oos-equity wf_oos_equity.csv
```

Notes:
- `--walk-forward` requires `--sweep` tokens to define the search space.
- Use `--cap-grid --max-evals N` to keep a grid sweep from exploding.

### Single sweep (Commit 5 still works)
```bash
python -m trading_backtester.cli --csv data.csv --strategy volatility_breakout \
  --sweep lookback=10:60:5 --sweep k=0.3:1.0:0.1 \
  --objective net_pct --out sweep.csv
```

## Next (Commit 7)

- Formal event stream (BarEvent, SignalEvent, FillEvent, EquityEvent)
- Step-through playback UI becomes trivial once events are explicit
