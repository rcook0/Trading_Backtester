from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

import pandas as pd

from .events import (
    BarEvent,
    SignalEvent,
    FillEvent,
    EquityEvent,
    TradeClosedEvent,
    EventBase,
    to_wire,
)

@dataclass(frozen=True)
class BacktestConfig:
    # Portfolio / risk
    initial_equity: float = 100_000.0
    risk_per_trade: float = 0.01           # fraction of equity risked per trade

    # Exits (percent of entry price)
    stop_loss_pct: float = 0.01
    take_profit_pct: float = 0.02
    trailing_pct: float = 0.0              # 0 disables
    allow_reverse: bool = True             # reverse on opposite signal

    # Commit 11: execution fidelity
    entry_slippage_bps: float = 0.0        # basis points; applied adverse to trade direction
    exit_slippage_bps: float = 0.0         # basis points; applied adverse to closing direction
    entry_latency_bars: int = 0            # 0 = same-bar (immediate), 1 = next bar open, etc.
    exit_latency_bars: int = 0

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

def _apply_slippage(price: float, action_side: str, bps: float) -> float:
    """Apply adverse slippage to a fill.

    action_side: the *action* being executed in the market (BUY pays more, SELL receives less).
    bps: basis points (1 bp = 0.01%).
    """
    if bps <= 0:
        return float(price)
    s = float(bps) / 10_000.0
    if action_side.upper() == "BUY":
        return float(price) * (1.0 + s)
    else:
        return float(price) * (1.0 - s)

def backtest(df: pd.DataFrame, signals: list[tuple], cfg: BacktestConfig) -> tuple[list[Trade], list[float]]:
    """Non-event backtest (kept for legacy)."""
    trades, curve, _ = backtest_with_events(df, signals, cfg, emit_events=False)
    return trades, curve

def backtest_with_events(
    df: pd.DataFrame,
    signals: list[tuple],
    cfg: BacktestConfig,
    emit_events: bool = True,
) -> tuple[list[Trade], list[float], list[dict[str, Any]]]:
    """Backtest that also produces a formal *wire* event stream.

    Wire stream drives:
    - Streamlit playback
    - Avalonia playback
    - future slippage/latency/manual overlays as additional events

    Returns:
      trades, equity_curve, wire_events
    """
    df = df.reset_index(drop=True)
    signals = sorted(signals, key=lambda x: x[0])
    sig_i = 0

    equity = float(cfg.initial_equity)
    curve: list[float] = []
    trades: list[Trade] = []
    internal_events: list[EventBase] = []

    def emit(ev: EventBase):
        if emit_events:
            internal_events.append(ev)

    # ---- position state ----
    side: str | None = None
    entry_time: Any | None = None
    entry_price: float = 0.0
    size: float = 0.0
    stop: float = 0.0
    take: float = 0.0
    best: float = 0.0  # best price since entry, for trailing

    # ---- pending orders (latency) ----
    pending_entry: dict[str, Any] | None = None
    pending_exit: dict[str, Any] | None = None

    def _risk_size(eq: float, price: float) -> float:
        risk_dollars = eq * cfg.risk_per_trade
        sl_dist = max(1e-9, cfg.stop_loss_pct * price)
        return float(risk_dollars / sl_dist)

    def open_pos(fill_time, s, executed_price, eq, *, intended_price=None, slippage_bps=0.0, latency_bars=0, submitted_time=None, reason="Signal"):
        nonlocal side, entry_time, entry_price, size, stop, take, best
        side = s
        entry_time = fill_time
        entry_price = float(executed_price)
        size = _risk_size(eq, float(executed_price))
        sl_dist = cfg.stop_loss_pct * float(executed_price)
        stop = float(executed_price) - sl_dist if side == "BUY" else float(executed_price) + sl_dist
        take = float(executed_price) + cfg.take_profit_pct * float(executed_price) if side == "BUY" else float(executed_price) - cfg.take_profit_pct * float(executed_price)
        best = float(executed_price)

        emit(FillEvent(
            time=fill_time,
            action="OPEN",
            side=side,
            price=float(executed_price),
            intended_price=float(intended_price) if intended_price is not None else None,
            slippage_bps=float(slippage_bps),
            latency_bars=int(latency_bars),
            submitted_time=submitted_time,
            qty=float(size),
            reason=reason
        ))

    def close_pos(fill_time, executed_price, reason, *, intended_price=None, slippage_bps=0.0, latency_bars=0, submitted_time=None):
        nonlocal side, entry_time, entry_price, size, equity, stop, take, best
        if side is None:
            return

        pnl = _pos_pnl(side, entry_price, float(executed_price), size)
        equity += pnl
        pnl_pct = (pnl / equity) if equity else 0.0

        trades.append(Trade(entry_time, side, float(entry_price), float(size), fill_time, float(executed_price), float(pnl), reason))

        emit(TradeClosedEvent(
            time=fill_time,
            side=side,
            entry_price=float(entry_price),
            exit_price=float(executed_price),
            qty=float(size),
            pnl=float(pnl),
            pnl_pct=float(pnl_pct),
            reason=reason
        ))

        # action_side is the market action that closes the position
        action_side = "SELL" if side == "BUY" else "BUY"
        emit(FillEvent(
            time=fill_time,
            action="CLOSE",
            side=side,
            price=float(executed_price),
            intended_price=float(intended_price) if intended_price is not None else None,
            slippage_bps=float(slippage_bps),
            latency_bars=int(latency_bars),
            submitted_time=submitted_time,
            qty=float(size),
            reason=reason
        ))

        side = None
        entry_time = None
        entry_price = 0.0
        size = 0.0
        stop = 0.0
        take = 0.0
        best = 0.0

    # ---- main loop ----
    for i, row in df.iterrows():
        t = row["time"]
        o = float(row["open"])
        h = float(row["high"])
        l = float(row["low"])
        c = float(row["close"])
        v = float(row["volume"]) if "volume" in row and not pd.isna(row["volume"]) else None

        emit(BarEvent(time=t, index=int(i), open=o, high=h, low=l, close=c, volume=v))

        # ---- execute pending exit first (so we don't open+close on same bar unless intended) ----
        if pending_exit is not None and side is not None:
            if int(pending_exit["remaining"]) <= 0:
                base_price = o if int(pending_exit["latency"]) > 0 else float(pending_exit["intended_price"])
                # closing direction is opposite of position side
                action_side = "SELL" if side == "BUY" else "BUY"
                exec_price = _apply_slippage(base_price, action_side, cfg.exit_slippage_bps)
                close_pos(
                    fill_time=t,
                    executed_price=exec_price,
                    reason=str(pending_exit["reason"]),
                    intended_price=float(pending_exit["intended_price"]),
                    slippage_bps=float(cfg.exit_slippage_bps),
                    latency_bars=int(pending_exit["latency"]),
                    submitted_time=pending_exit.get("submitted_time"),
                )
                pending_exit = None
            else:
                pending_exit["remaining"] = int(pending_exit["remaining"]) - 1

        # ---- execute pending entry ----
        if pending_entry is not None and side is None:
            if int(pending_entry["remaining"]) <= 0:
                base_price = o if int(pending_entry["latency"]) > 0 else float(pending_entry["intended_price"])
                exec_price = _apply_slippage(base_price, pending_entry["side"], cfg.entry_slippage_bps)
                open_pos(
                    fill_time=t if int(pending_entry["latency"]) > 0 else pending_entry.get("submitted_time", t),
                    s=pending_entry["side"],
                    executed_price=exec_price,
                    eq=equity,
                    intended_price=float(pending_entry["intended_price"]),
                    slippage_bps=float(cfg.entry_slippage_bps),
                    latency_bars=int(pending_entry["latency"]),
                    submitted_time=pending_entry.get("submitted_time"),
                    reason=str(pending_entry["reason"]),
                )
                pending_entry = None
            else:
                pending_entry["remaining"] = int(pending_entry["remaining"]) - 1

        # ---- consume any signals <= this bar time ----
        while sig_i < len(signals) and signals[sig_i][0] <= t:
            st, sside, sprice = signals[sig_i]
            sig_i += 1
            sside = str(sside).upper()
            sprice = float(sprice)

            emit(SignalEvent(time=st, side=sside, price=float(sprice), source="strategy"))

            if side is None and pending_entry is None:
                pending_entry = {
                    "side": sside,
                    "intended_price": sprice,
                    "reason": "Signal",
                    "latency": int(cfg.entry_latency_bars),
                    "remaining": int(cfg.entry_latency_bars),
                    "submitted_time": st,
                }
            elif side is not None and cfg.allow_reverse and side != sside:
                # Reverse: schedule exit immediately (or with exit latency), then schedule entry.
                if pending_exit is None:
                    # close at bar close price baseline (intended) unless latency>0 then next open
                    pending_exit = {
                        "intended_price": float(c),
                        "reason": "ReverseSignal",
                        "latency": int(cfg.exit_latency_bars),
                        "remaining": int(cfg.exit_latency_bars),
                        "submitted_time": t,
                    }
                if pending_entry is None:
                    pending_entry = {
                        "side": sside,
                        "intended_price": sprice,
                        "reason": "ReverseSignal",
                        "latency": int(cfg.entry_latency_bars),
                        "remaining": int(cfg.entry_latency_bars),
                        "submitted_time": st,
                    }

        # ---- exit checks (if still in a position and no exit pending) ----
        if side is not None and pending_exit is None:
            best = max(best, h) if side == "BUY" else min(best, l)

            hit_stop = (l <= stop) if side == "BUY" else (h >= stop)
            hit_take = (h >= take) if side == "BUY" else (l <= take)

            if hit_stop:
                pending_exit = {
                    "intended_price": float(stop),
                    "reason": "StopLoss",
                    "latency": int(cfg.exit_latency_bars),
                    "remaining": int(cfg.exit_latency_bars),
                    "submitted_time": t,
                }
            elif hit_take:
                pending_exit = {
                    "intended_price": float(take),
                    "reason": "TakeProfit",
                    "latency": int(cfg.exit_latency_bars),
                    "remaining": int(cfg.exit_latency_bars),
                    "submitted_time": t,
                }
            elif cfg.trailing_pct and cfg.trailing_pct > 0:
                trail_dist = cfg.trailing_pct * entry_price
                trail = (best - trail_dist) if side == "BUY" else (best + trail_dist)
                hit_trail = (l <= trail) if side == "BUY" else (h >= trail)
                if hit_trail:
                    pending_exit = {
                        "intended_price": float(trail),
                        "reason": "TrailingStop",
                        "latency": int(cfg.exit_latency_bars),
                        "remaining": int(cfg.exit_latency_bars),
                        "submitted_time": t,
                    }

        curve.append(equity)
        emit(EquityEvent(time=t, equity=float(equity)))

    # close at end (immediate fill on last close with exit slippage)
    if side is not None:
        base_price = float(df.iloc[-1]["close"])
        action_side = "SELL" if side == "BUY" else "BUY"
        exec_price = _apply_slippage(base_price, action_side, cfg.exit_slippage_bps)
        close_pos(df.iloc[-1]["time"], exec_price, "EndOfData",
                  intended_price=base_price, slippage_bps=float(cfg.exit_slippage_bps),
                  latency_bars=0, submitted_time=df.iloc[-1]["time"])
        curve[-1] = equity
        emit(EquityEvent(time=df.iloc[-1]["time"], equity=float(equity)))

    wire_events = [to_wire(ev) for ev in internal_events] if emit_events else []
    return trades, curve, wire_events
