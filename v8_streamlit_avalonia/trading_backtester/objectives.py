from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal
import math

from .metrics import Metrics

ObjectiveName = Literal[
    "net_pct",
    "max_drawdown_pct",
    "profit_factor",
    "win_rate",
    "score_balanced",
]

@dataclass(frozen=True)
class Objective:
    name: ObjectiveName
    direction: Literal["max","min"]
    fn: Callable[[Metrics], float]
    help: str

def _finite(x: float, cap: float = 1e9) -> float:
    if x is None:
        return float("-inf")
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return cap if x > 0 else -cap
    return float(x)

OBJECTIVES: dict[ObjectiveName, Objective] = {
    "net_pct": Objective("net_pct","max",lambda m: _finite(m.net_pct), "Maximize total return (final/initial - 1)."),
    "max_drawdown_pct": Objective("max_drawdown_pct","min",lambda m: _finite(m.max_drawdown_pct), "Minimize maximum drawdown."),
    "profit_factor": Objective("profit_factor","max",lambda m: _finite(m.profit_factor, cap=1000.0), "Maximize profit factor (gross profit / gross loss)."),
    "win_rate": Objective("win_rate","max",lambda m: _finite(m.win_rate), "Maximize win rate."),
    "score_balanced": Objective("score_balanced","max",lambda m: _finite(m.net_pct) - 0.5 * _finite(m.max_drawdown_pct), "Balanced score: net_pct - 0.5 * max_drawdown_pct."),
}

def get_objective(name: str) -> Objective:
    key = name.strip()
    if key not in OBJECTIVES:
        raise KeyError(f"Unknown objective '{name}'. Known: {sorted(OBJECTIVES.keys())}")
    return OBJECTIVES[key]
