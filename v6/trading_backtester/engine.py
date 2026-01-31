from __future__ import annotations

from dataclasses import dataclass
import math
import pandas as pd

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

def backtest(df: pd.DataFrame, signals: list[tuple], cfg: BacktestConfig) -> tuple[list[Trade], list[float]]:
    """Backtest with simple single-position execution.

    signals: list of tuples (time, side, price) where side in {'BUY','SELL'}.
    Execution model: signal triggers entry/reversal at bar close price.
    Exits: intra-bar high/low checks against SL/TP/trailing stop (percent based).
    """
    df = df.reset_index(drop=True)
    signals = sorted(signals, key=lambda x: x[0])
    sig_i = 0

    equity = cfg.initial_equity
    curve = []
    trades: list[Trade] = []

    # position state
    side = None
    entry_time = None
    entry_price = None
    size = 0.0
    stop = None
    take = None
    best = None

    def open_pos(t, s, price, eq):
        nonlocal side, entry_time, entry_price, size, stop, take, best
        risk = max(0.0, cfg.risk_per_trade) * eq
        stop_dist = max(1e-9, cfg.stop_loss_pct) * price
        size = risk / stop_dist
        side = s
        entry_time = t
        entry_price = price
        stop = price - stop_dist if s == "BUY" else price + stop_dist
        take = price + (cfg.take_profit_pct * price) if s == "BUY" else price - (cfg.take_profit_pct * price)
        best = price

    def close_pos(t, price, reason):
        nonlocal side, entry_time, entry_price, size, stop, take, best, equity
        pnl = _pos_pnl(side, entry_price, price, size)
        trades.append(Trade(entry_time, side, entry_price, size, t, price, pnl, reason))
        equity += pnl
        side = None
        entry_time = None
        entry_price = None
        size = 0.0
        stop = None
        take = None
        best = None

    for i in range(len(df)):
        row = df.iloc[i]
        t = row["time"]
        o,h,l,c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])

        # apply any signals up to bar time
        while sig_i < len(signals) and signals[sig_i][0] <= t:
            st, sside, sprice = signals[sig_i]
            sig_i += 1
            sprice = float(sprice)
            if side is None:
                open_pos(st, sside, sprice, equity)
            else:
                if cfg.allow_reverse and side != sside:
                    close_pos(t, c, "ReverseSignal")
                    open_pos(st, sside, sprice, equity)

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

    # close at end
    if side is not None:
        close_pos(df.iloc[-1]["time"], float(df.iloc[-1]["close"]), "EndOfData")
        curve[-1] = equity

    return trades, curve
