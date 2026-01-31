from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json

import pandas as pd

from .catalog import get_strategy, StrategySurface
from .engine import BacktestConfig, backtest
from .metrics import compute_metrics, Metrics
from .objectives import get_objective, Objective
from .optimize import sweep, SweepConfig

@dataclass(frozen=True)
class WalkForwardConfig:
    train_days: int = 180
    test_days: int = 30
    step_days: int = 30
    objective: str = "score_balanced"
    sweep_mode: str = "grid"       # "grid" | "random"
    max_evals: int = 500           # random evals (and optional grid cap)
    cap_grid: bool = True          # cap grid to max_evals to avoid combinatorial explosions
    seed: int = 12345

def _ensure_time(df: pd.DataFrame) -> pd.Series:
    if "time" not in df.columns:
        raise ValueError("Normalized dataframe must contain 'time' column.")
    t = pd.to_datetime(df["time"])
    return t

def _slice(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    t = _ensure_time(df)
    m = (t >= start) & (t < end)
    return df.loc[m].reset_index(drop=True)

def _params_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k.replace("param_",""): v for k, v in row.items() if str(k).startswith("param_")}

def _param_drift(prev: dict[str, Any] | None, cur: dict[str, Any] | None) -> float:
    if not prev or not cur:
        return 0.0
    keys = sorted(set(prev.keys()) | set(cur.keys()))
    drift = 0.0
    for k in keys:
        a = prev.get(k)
        b = cur.get(k)
        if a == b:
            continue
        # numeric drift
        if isinstance(a, (int,float)) and isinstance(b, (int,float)):
            drift += abs(float(a) - float(b))
        else:
            drift += 1.0
    return float(drift)

def walk_forward(
    df: pd.DataFrame,
    strategy_key: str,
    sweep_tokens: list[str],
    bt_cfg: BacktestConfig,
    wf_cfg: WalkForwardConfig = WalkForwardConfig(),
    sweep_cfg: SweepConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Walk-forward optimization + OOS evaluation.

    For each window:
      1) Optimize params on TRAIN segment (using sweep tokens/objective)
      2) Apply best params to TEST segment
      3) Record both train/test metrics + parameter stability signals

    Returns:
      windows_df: one row per walk-forward window
      oos_equity_df: concatenated OOS equity curves with window id
    """
    strat = get_strategy(strategy_key)
    obj = get_objective(wf_cfg.objective)

    t = _ensure_time(df)
    df_sorted = df.copy()
    df_sorted["time"] = pd.to_datetime(t)
    df_sorted = df_sorted.sort_values("time").reset_index(drop=True)

    start = df_sorted["time"].iloc[0].normalize()
    end = df_sorted["time"].iloc[-1]

    train_delta = pd.Timedelta(days=wf_cfg.train_days)
    test_delta = pd.Timedelta(days=wf_cfg.test_days)
    step_delta = pd.Timedelta(days=wf_cfg.step_days)

    if sweep_cfg is None:
        sweep_cfg = SweepConfig(
            mode=wf_cfg.sweep_mode, 
            max_evals=max(1, wf_cfg.max_evals),
            cap_grid=(wf_cfg.max_evals if wf_cfg.cap_grid else None),
            seed=wf_cfg.seed,
        )

    rows = []
    oos_curves = []

    window_id = 0
    cursor = start + train_delta
    prev_best: dict[str, Any] | None = None

    while cursor + test_delta <= end:
        train_start = cursor - train_delta
        train_end = cursor
        test_start = cursor
        test_end = cursor + test_delta

        train_df = _slice(df_sorted, train_start, train_end)
        test_df = _slice(df_sorted, test_start, test_end)

        if len(train_df) < 50 or len(test_df) < 10:
            cursor += step_delta
            continue

        # optimize on train
        sweep_df = sweep(
            df=train_df,
            strategy_key=strat.key,
            grid_tokens=sweep_tokens,
            cfg=bt_cfg,
            objective_name=wf_cfg.objective,
            sweep_cfg=sweep_cfg,
        )

        if sweep_df.empty:
            cursor += step_delta
            continue

        best_row = sweep_df.iloc[0].to_dict()
        best_params = _params_from_row(best_row)

        # train metrics for best params
        train_signals = strat.run(train_df, best_params)
        train_trades, train_curve = backtest(train_df, train_signals, bt_cfg)
        train_m = compute_metrics(bt_cfg.initial_equity, train_curve, train_trades)

        # test metrics for best params (OOS)
        test_signals = strat.run(test_df, best_params)
        test_trades, test_curve = backtest(test_df, test_signals, bt_cfg)
        test_m = compute_metrics(bt_cfg.initial_equity, test_curve, test_trades)

        # stability diagnostics
        drift = _param_drift(prev_best, best_params)
        prev_best = best_params

        perf_decay = None
        if train_m.net_pct is not None and train_m.net_pct != 0:
            perf_decay = float(test_m.net_pct / train_m.net_pct)

        row = {
            "window_id": window_id,
            "train_start": train_start,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
            "best_params_json": json.dumps(best_params, default=str),

            "train_net_pct": train_m.net_pct,
            "train_max_drawdown_pct": train_m.max_drawdown_pct,
            "train_profit_factor": train_m.profit_factor,
            "train_win_rate": train_m.win_rate,
            "train_total_trades": train_m.total_trades,

            "test_net_pct": test_m.net_pct,
            "test_max_drawdown_pct": test_m.max_drawdown_pct,
            "test_profit_factor": test_m.profit_factor,
            "test_win_rate": test_m.win_rate,
            "test_total_trades": test_m.total_trades,

            "param_drift": drift,
            "performance_decay": perf_decay,
            "train_objective_value": obj.fn(train_m),
            "test_objective_value": obj.fn(test_m),
        }
        rows.append(row)

        # attach OOS equity curve with timestamps
        curve_df = pd.DataFrame({
            "window_id": window_id,
            "time": test_curve["time"],
            "equity": test_curve["equity"],
        })
        oos_curves.append(curve_df)

        window_id += 1
        cursor += step_delta

    windows_df = pd.DataFrame(rows)
    oos_df = pd.concat(oos_curves, ignore_index=True) if oos_curves else pd.DataFrame(columns=["window_id","time","equity"])
    return windows_df, oos_df
