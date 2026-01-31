from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal
import itertools
import random

import pandas as pd

from .catalog import get_strategy
from .engine import BacktestConfig, backtest
from .metrics import compute_metrics, Metrics
from .objectives import get_objective, Objective
from .params import ParamSpec, merge_params

SearchMode = Literal["grid", "random"]

@dataclass(frozen=True)
class SweepConfig:
    mode: SearchMode = "grid"
    max_evals: int = 2000          # random mode evals
    cap_grid: int | None = None    # optional cap for grid
    seed: int = 12345

@dataclass(frozen=True)
class EvalResult:
    params: dict[str, Any]
    metrics: Metrics
    objective_value: float

def _frange(start: float, stop: float, step: float) -> list[float]:
    if step == 0:
        raise ValueError("step cannot be 0")
    vals = []
    x = start
    if step > 0:
        while x <= stop + 1e-12:
            vals.append(float(x))
            x += step
    else:
        while x >= stop - 1e-12:
            vals.append(float(x))
            x += step
    return vals

def parse_sweep_tokens(tokens: list[str], schema: list[ParamSpec]) -> dict[str, list[Any]]:
    """Parse sweep tokens like:
    - window=10:60:5
    - sigma=1.5:3.0:0.25
    - fade_extremes=true,false
    - window=* (auto grid from ParamSpec min/max/step)
    """
    spec_map = {p.key: p for p in schema}
    grid: dict[str, list[Any]] = {}
    for tok in tokens:
        if "=" not in tok:
            raise ValueError(f"Bad sweep token '{tok}'. Use key=...")
        key, rhs = tok.split("=", 1)
        key = key.strip()
        if key not in spec_map:
            raise KeyError(f"Unknown param '{key}'. Known: {sorted(spec_map.keys())}")
        ps = spec_map[key]
        rhs = rhs.strip()

        if rhs == "*":
            if ps.min is None or ps.max is None or ps.step is None:
                raise ValueError(f"Param '{key}' has no min/max/step; cannot use '*' auto-grid.")
            if ps.type == "int":
                grid[key] = list(range(int(ps.min), int(ps.max) + 1, int(ps.step)))
            elif ps.type == "float":
                grid[key] = _frange(float(ps.min), float(ps.max), float(ps.step))
            else:
                raise ValueError(f"Auto-grid '*' not supported for type {ps.type}")
            continue

        if "," in rhs and ":" not in rhs:
            parts = [p.strip() for p in rhs.split(",") if p.strip() != ""]
            vals: list[Any] = []
            for p in parts:
                if ps.type == "bool":
                    vals.append(p.lower() in ("1","true","t","yes","y","on"))
                elif ps.type == "int":
                    vals.append(int(float(p)))
                elif ps.type == "float":
                    vals.append(float(p))
                else:
                    vals.append(p)
            grid[key] = vals
            continue

        if ":" in rhs:
            parts = [p.strip() for p in rhs.split(":")]
            if len(parts) != 3:
                raise ValueError(f"Bad range '{rhs}' for '{key}'. Use a:b:c")
            a, b, c = (float(parts[0]), float(parts[1]), float(parts[2]))
            if ps.type == "int":
                step = int(c)
                if step == 0:
                    raise ValueError("int range step cannot be 0")
                end = int(b) + (1 if step > 0 else -1)
                grid[key] = list(range(int(a), end, step))
            elif ps.type == "float":
                grid[key] = _frange(a, b, c)
            else:
                raise ValueError(f"Range sweep not supported for type {ps.type}")
            continue

        # singleton literal
        if ps.type == "bool":
            grid[key] = [rhs.lower() in ("1","true","t","yes","y","on")]
        elif ps.type == "int":
            grid[key] = [int(float(rhs))]
        elif ps.type == "float":
            grid[key] = [float(rhs)]
        else:
            grid[key] = [rhs]
    return grid

def _grid_param_sets(grid: dict[str, list[Any]]) -> Iterable[dict[str, Any]]:
    keys = list(grid.keys())
    if not keys:
        yield {}
        return
    for combo in itertools.product(*(grid[k] for k in keys)):
        yield dict(zip(keys, combo))

def _random_param_set(schema: list[ParamSpec], grid: dict[str, list[Any]], rng: random.Random) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ps in schema:
        if ps.key in grid:
            out[ps.key] = rng.choice(grid[ps.key])
            continue
        if ps.type == "int" and ps.min is not None and ps.max is not None:
            out[ps.key] = rng.randint(int(ps.min), int(ps.max))
        elif ps.type == "float" and ps.min is not None and ps.max is not None:
            out[ps.key] = rng.uniform(float(ps.min), float(ps.max))
        else:
            out[ps.key] = ps.default
    return out

def evaluate_once(df: pd.DataFrame, strat, overrides: dict[str, Any], cfg: BacktestConfig, objective: Objective):
    signals = strat.run(df, overrides)
    trades, curve = backtest(df, signals, cfg)
    metrics = compute_metrics(cfg.initial_equity, curve, trades)
    val = objective.fn(metrics)
    return EvalResult(overrides, metrics, val)

def sweep(
    df: pd.DataFrame,
    strategy_key: str,
    grid_tokens: list[str],
    cfg: BacktestConfig,
    objective_name: str = "score_balanced",
    sweep_cfg: SweepConfig = SweepConfig(),
) -> pd.DataFrame:
    strat = get_strategy(strategy_key)
    objective = get_objective(objective_name)
    grid = parse_sweep_tokens(grid_tokens, strat.params) if grid_tokens else {}

    rng = random.Random(sweep_cfg.seed)
    results: list[EvalResult] = []
    evals = 0

    if sweep_cfg.mode == "grid":
        for params in _grid_param_sets(grid):
            merged = merge_params(params, strat.params)
            results.append(evaluate_once(df, strat, merged, cfg, objective))
            evals += 1
            if sweep_cfg.cap_grid is not None and evals >= sweep_cfg.cap_grid:
                break
    elif sweep_cfg.mode == "random":
        for _ in range(max(1, sweep_cfg.max_evals)):
            params = _random_param_set(strat.params, grid, rng)
            merged = merge_params(params, strat.params)
            results.append(evaluate_once(df, strat, merged, cfg, objective))
    else:
        raise ValueError(f"Unknown sweep mode '{sweep_cfg.mode}'")

    rows = []
    for r in results:
        row = {
            "objective_value": r.objective_value,
            "net_pct": r.metrics.net_pct,
            "max_drawdown_pct": r.metrics.max_drawdown_pct,
            "profit_factor": r.metrics.profit_factor,
            "win_rate": r.metrics.win_rate,
            "total_trades": r.metrics.total_trades,
        }
        for k, v in r.params.items():
            row[f"param_{k}"] = v
        rows.append(row)

    out = pd.DataFrame(rows)
    if not out.empty:
        ascending = (objective.direction == "min")
        out = out.sort_values("objective_value", ascending=ascending).reset_index(drop=True)
    return out
