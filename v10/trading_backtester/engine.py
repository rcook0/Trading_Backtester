from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Optional, Sequence

import pandas as pd

from .events import BarEvent, SignalEvent, FillEvent, EquityEvent, TradeClosedEvent, EventBase

@dataclass(frozen=True)
class BacktestConfig:
    initial_equity: float = 100_000.0
    risk_per_trade: float = 0.01           # fraction of equity
    stop_loss_pct: float = 0.01            # percent of entry price
    take_profit_pct: float = 0.02          # percent of entry price
    trailing_pct: float = 0.0              # 0 disables
    allow_reverse: bool = True             # reverse on opposite signal

@dataclass(frozen=True)
class Trade:
    entry_time: object
    side: str
    entry_price: float
    size: float
    exit_time: object
    exit_price: float
    pnl: float
    reason: str

def _pos_pnl(side: str, entry: float, exit: float, size: float) -> float:
    return (exit - entry) * size if side == "BUY" else (entry - exit) * size

EventSink = Callable[[EventBase], None]

def backtest(df: pd.DataFrame, signals: list[tuple], cfg: BacktestConfig) -> tuple[list[Trade], list[float]]:
    """Backtest with simple single-position execution.

    signals: list of tuples (time, side, price) where side in {'BUY','SELL'}.
    Execution model: signal triggers entry/reversal at bar close price.
    Exits: intra-bar high/low checks against SL/TP/trailing stop (percent based).

    Returns:
      trades: list[Trade]
      equity_curve: list[float] aligned with df rows
    """
    trades, curve, _events = backtest_with_events(df, signals, cfg, emit_events=False)
    return trades, curve

def backtest_with_events(
    df: pd.DataFrame,
    signals: list[tuple],
    cfg: BacktestConfig,
    emit_events: bool = True,
) -> tuple[list[Trade], list[float], list[EventBase]]:
    """Backtest that also produces a formal event stream.

    Event stream is designed to drive:
    - step-through playback
    - UI widgets (fills, PnL, equity)
    - debugging / reproducibility

    Returns:
      trades, equity_curve, events
    """
    df = df.reset_index(drop=True)
    signals = sorted(signals, key=lambda x: x[0])
    sig_i = 0

    equity = float(cfg.initial_equity)
    curve: list[float] = []
    trades: list[Trade] = []
    events: list[EventBase] = []

    def emit(ev: EventBase):
        if emit_events:
            events.append(ev)

    # position state
    side: str | None = None
    entry_time: Any | None = None
    entry_price: float = 0.0
    size: float = 0.0
    stop: float = 0.0
    take: float = 0.0
    best: float = 0.0  # best price since entry, for trailing

    def open_pos(t, s, price, eq, reason="Signal"):
        nonlocal side, entry_time, entry_price, size, stop, take, best
        # position sizing: risk_per_trade dollars / stop distance
        risk_dollars = eq * cfg.risk_per_trade
        sl_dist = cfg.stop_loss_pct * price
        if sl_dist <= 0:
            return
        size_calc = risk_dollars / sl_dist
        side = s
        entry_time = t
        entry_price = price
        size = float(size_calc)
        stop = price - sl_dist if side == "BUY" else price + sl_dist
        take = price + cfg.take_profit_pct * price if side == "BUY" else price - cfg.take_profit_pct * price
        best = price
        emit(FillEvent(time=t, action="OPEN", side=side, price=float(price), size=float(size), reason=reason))

    def close_pos(t, price, reason):
        nonlocal side, entry_time, entry_price, size, equity, stop, take, best
        if side is None:
            return
        pnl = _pos_pnl(side, entry_price, price, size)
        equity += pnl
        trades.append(Trade(entry_time, side, float(entry_price), float(size), t, float(price), float(pnl), reason))
        emit(TradeClosedEvent(time=t, side=side, entry_price=float(entry_price), exit_price=float(price), size=float(size), pnl=float(pnl), reason=reason))
        emit(FillEvent(time=t, action="CLOSE", side=side, price=float(price), size=float(size), reason=reason))
        side = None
        entry_time = None
        entry_price = 0.0
        size = 0.0
        stop = 0.0
        take = 0.0
        best = 0.0

    for i, row in df.iterrows():
        t = row["time"]
        o = float(row["open"])
        h = float(row["high"])
        l = float(row["low"])
        c = float(row["close"])
        v = float(row["volume"]) if "volume" in row and not pd.isna(row["volume"]) else None

        emit(BarEvent(time=t, index=int(i), open=o, high=h, low=l, close=c, volume=v))

        # consume any signals <= this bar time
        while sig_i < len(signals) and signals[sig_i][0] <= t:
            st, sside, sprice = signals[sig_i]
            sig_i += 1
            sside = str(sside).upper()
            sprice = float(sprice)
            emit(SignalEvent(time=st, side=sside, price=float(sprice), source="strategy"))

            if side is None:
                open_pos(st, sside, sprice, equity, reason="Signal")
            else:
                if cfg.allow_reverse and side != sside:
                    # close at bar close for reversal
                    emit(FillEvent(time=t, action="REVERSE", side=side, price=float(c), size=float(size), reason="ReverseSignal"))
                    close_pos(t, c, "ReverseSignal")
                    open_pos(st, sside, sprice, equity, reason="ReverseSignal")

        # exit checks
        if side is not None:
            best = max(best, h) if side == "BUY" else min(best, l)

            hit_stop = (l <= stop) if side == "BUY" else (h >= stop)
            hit_take = (h >= take) if side == "BUY" else (l <= take)
            if hit_stop:
                close_pos(t, float(stop), "StopLoss")
            elif hit_take:
                close_pos(t, float(take), "TakeProfit")
            elif cfg.trailing_pct and cfg.trailing_pct > 0:
                trail_dist = cfg.trailing_pct * entry_price
                trail = (best - trail_dist) if side == "BUY" else (best + trail_dist)
                hit_trail = (l <= trail) if side == "BUY" else (h >= trail)
                if hit_trail:
                    close_pos(t, float(trail), "TrailingStop")

        curve.append(equity)
        emit(EquityEvent(time=t, equity=float(equity)))

    # close at end
    if side is not None:
        close_pos(df.iloc[-1]["time"], float(df.iloc[-1]["close"]), "EndOfData")
        curve[-1] = equity
        emit(EquityEvent(time=df.iloc[-1]["time"], equity=float(equity)))

    return trades, curve, events
