from __future__ import annotations

from dataclasses import dataclass
import math
from .engine import Trade

@dataclass(frozen=True)
class Metrics:
    total_trades: int
    win_rate: float
    net_pct: float
    max_drawdown_pct: float
    profit_factor: float

def compute_metrics(initial_equity: float, equity_curve: list[float], trades: list[Trade]) -> Metrics:
    if not equity_curve:
        return Metrics(0, 0.0, 0.0, 0.0, 0.0)

    final_eq = equity_curve[-1]
    net_pct = (final_eq / initial_equity - 1.0) if initial_equity else 0.0

    peak = equity_curve[0]
    max_dd = 0.0
    for e in equity_curve:
        peak = max(peak, e)
        dd = (peak - e) / peak if peak else 0.0
        max_dd = max(max_dd, dd)

    wins = sum(1 for t in trades if t.pnl > 0)
    total = len(trades)
    win_rate = (wins / total) if total else 0.0

    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = -sum(t.pnl for t in trades if t.pnl < 0)
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (math.inf if gross_profit > 0 else 0.0)

    return Metrics(total, win_rate, net_pct, max_dd, profit_factor)
