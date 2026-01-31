# trading_backtester — Commit 7 (Formal Event Stream)

Commit 4: uniform strategy parameter surface  
Commit 5: parameter sweeps & optimization  
Commit 6: walk-forward + OOS validation  
**Commit 7: formal event stream** ✅

## What Commit 7 does

The execution engine can now emit a **typed event stream** suitable for:

- bar-by-bar playback (step/auto-play)
- UI consumption (fills, signals, equity)
- debugging and reproducibility

New module: `trading_backtester/events.py`

Event types:
- `BarEvent`: OHLCV per bar
- `SignalEvent`: strategy signal (BUY/SELL)
- `FillEvent`: open/close/reverse actions
- `TradeClosedEvent`: realized PnL and reason
- `EquityEvent`: equity snapshot per bar

Engine API:
- `backtest(df, signals, cfg)` → (trades, equity_curve)  **(unchanged)**
- `backtest_with_events(df, signals, cfg)` → (trades, equity_curve, events)

## CLI: emit events (JSONL)

Single-run mode can write JSONL events:

```bash
python -m trading_backtester.cli --csv data.csv --strategy sigma_extreme \
  --param window=50 --param sigma=2.0 \
  --events-out events.jsonl
```

Each line is one JSON object (easy to stream + replay).

## Next (Commit 8)

- Build a step-through player that consumes events:
  - play/pause, speed slider (bars/sec)
  - chart overlay synced to BarEvent
  - fills + trades synced to Fill/TradeClosed
- Then Avalonia UI can be a pure event consumer.


## Commit 8 — Streamlit UI (event-driven)

Run:

```bash
pip install -e .
streamlit run app.py
```

Workflow:
1) Upload OHLCV CSV
2) Pick strategy + params (auto from ParamSpec)
3) Run backtest => events
4) Replay via cursor slider / step
5) Export events.jsonl (Avalonia will consume the same stream)


## Avalonia skeleton (Commit 8 add-on)

Build/run (Windows):

```powershell
cd src\Backtester.Avalonia
dotnet restore
dotnet run
```

The Avalonia app is intentionally minimal: it loads `events.jsonl` and provides cursor controls.
Charts/markers are the next step (Commit 9) and will still consume the same event stream.


## Commit 9 — Avalonia charts + replay state

Avalonia now renders:
- Candlestick chart (BarEvent)
- Equity line chart (EquityEvent)
- Fill markers (FillEvent)
- Position + unrealized PnL reconstructed from fills

Run:

```powershell
cd src\Backtester.Avalonia
dotnet restore
dotnet run
```


## Commit 10 — Interactive playback & execution fidelity

Avalonia:
- Play/Pause with speed (1–30 bars/sec)
- Keyboard controls: Space play/pause, ←/→ step, Shift+→ fast-forward
- Trade blotter list (tail of TradeClosedEvent)
- Entry price annotation for active position (foundation for SL/TP lines)

Streamlit:
- Play/Pause with deterministic stepping via auto-refresh
- Speed slider (1–30 bars/sec)
- Jump-to-time (nearest BarEvent)
- Trade blotter table

Foundation for future commits:
- Slippage, latency, and manual overlays should be modeled as new event types (no UI recompute).


## Commit 11 — Slippage, latency, and deterministic replay contract

This commit adds execution-fidelity plumbing while keeping the core rule:
**UIs render from events; they do not compute execution.**

### What changed
- Engine now returns *wire events* as dicts: `{time, type, payload}` for cross-UI compatibility.
- BacktestConfig adds:
  - `entry_slippage_bps`, `exit_slippage_bps`
  - `entry_latency_bars`, `exit_latency_bars`
- FillEvent payload now includes:
  - `intended_price`, `slippage_bps`, `latency_bars`, `submitted_time`
- Latency model (bar-based):
  - `0` = immediate (same bar)
  - `1` = next bar open
  - `N` = N bars later open

### Why this matters
These fields are the foundation for later:
- spread models (bid/ask as event fields)
- stochastic slippage distributions
- latency jitter distributions
- manual/discretionary overlays as new event types
