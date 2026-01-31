from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import list_strategies, get_strategy
from .data import load_csv_ohlcv
from .engine import BacktestConfig, backtest
from .metrics import compute_metrics
from .params import parse_kv_list
from .objectives import OBJECTIVES
from .optimize import sweep, SweepConfig
from .walkforward import walk_forward, WalkForwardConfig

def main(argv=None):
    ap = argparse.ArgumentParser(prog="trading_backtester")

    ap.add_argument("--list", action="store_true", help="List available strategies")
    ap.add_argument("--describe", default=None, help="Print description + params for a strategy")
    ap.add_argument("--objectives", action="store_true", help="List available optimization objectives")

    ap.add_argument("--strategy", default="sigma_extreme", help="Strategy key or name")
    ap.add_argument("--param", action="append", default=[], help="Override strategy param: key=value (repeatable)")
    ap.add_argument("--csv", default=None, help="Path to OHLCV CSV (time,open,high,low,close,volume)")

    # execution model
    ap.add_argument("--sl", type=float, default=0.01, help="Stop loss pct (0.01=1%)")
    ap.add_argument("--tp", type=float, default=0.02, help="Take profit pct")
    ap.add_argument("--trail", type=float, default=0.0, help="Trailing pct (0 disables)")
    ap.add_argument("--risk", type=float, default=0.01, help="Risk per trade fraction of equity")

    # sweep / optimization
    ap.add_argument("--sweep", action="append", default=[], help="Sweep token: key=a:b:c OR key=v1,v2 OR key=* (repeatable)")
    ap.add_argument("--sweep-mode", choices=["grid","random"], default="grid", help="Sweep mode")
    ap.add_argument("--max-evals", type=int, default=500, help="Random evals (and optional cap for grid)")
    ap.add_argument("--cap-grid", action="store_true", help="Cap grid to --max-evals evaluations")
    ap.add_argument("--objective", default="score_balanced", help=f"Objective. Known: {sorted(OBJECTIVES.keys())}")
    ap.add_argument("--out", default=None, help="Write sweep or walk-forward primary results CSV to this path")

    # walk-forward
    ap.add_argument("--walk-forward", action="store_true", help="Run walk-forward optimization + out-of-sample evaluation")
    ap.add_argument("--train-days", type=int, default=180, help="Walk-forward training window (days)")
    ap.add_argument("--test-days", type=int, default=30, help="Walk-forward test window (days)")
    ap.add_argument("--step-days", type=int, default=30, help="Walk-forward step size (days)")
    ap.add_argument("--out-oos-equity", default=None, help="If set, write concatenated OOS equity curve CSV to this path")

    args = ap.parse_args(argv)

    if args.list:
        for s in list_strategies():
            print(f"{s.key:28}  {s.name}")
        return 0

    if args.objectives:
        for k, o in OBJECTIVES.items():
            print(f"{k:18} ({o.direction})  {o.help}")
        return 0

    if args.describe:
        s = get_strategy(args.describe)
        print(f"{s.name} ({s.key})")
        print(s.description)
        print("\nParams:")
        for p in s.params:
            rng = ""
            if p.min is not None or p.max is not None:
                rng = f" [{'' if p.min is None else p.min}..{'' if p.max is None else p.max}]"
            step = f" step={p.step}" if p.step is not None else ""
            print(f"  - {p.key} ({p.type}) default={p.default}{rng}{step}  {p.help}")
        return 0

    if not args.csv:
        raise SystemExit("--csv is required.")

    df = load_csv_ohlcv(args.csv)
    strat = get_strategy(args.strategy)

    bt_cfg = BacktestConfig(
        risk_per_trade=args.risk,
        stop_loss_pct=args.sl,
        take_profit_pct=args.tp,
        trailing_pct=args.trail,
    )

    # Walk-forward mode
    if args.walk_forward:
        if not args.sweep:
            raise SystemExit("--walk-forward requires at least one --sweep token (define the search space).")

        wf_cfg = WalkForwardConfig(
            train_days=max(1, args.train_days),
            test_days=max(1, args.test_days),
            step_days=max(1, args.step_days),
            objective=args.objective,
            sweep_mode=args.sweep_mode,
            max_evals=max(1, args.max_evals),
            cap_grid=args.cap_grid,
            seed=12345,
        )

        sweep_cfg = SweepConfig(
            mode=args.sweep_mode,
            max_evals=max(1, args.max_evals),
            cap_grid=(args.max_evals if args.cap_grid else None),
            seed=12345,
        )

        windows_df, oos_df = walk_forward(
            df=df,
            strategy_key=strat.key,
            sweep_tokens=args.sweep,
            bt_cfg=bt_cfg,
            wf_cfg=wf_cfg,
            sweep_cfg=sweep_cfg,
        )

        print(f"Walk-forward: {strat.name} ({strat.key}) objective={args.objective}")
        print(f"Windows: {len(windows_df)}")
        if len(windows_df) > 0:
            # crude aggregate on test set
            avg_net = windows_df["test_net_pct"].mean()
            avg_dd = windows_df["test_max_drawdown_pct"].mean()
            avg_pf = windows_df["test_profit_factor"].replace([float('inf')], float('nan')).mean()
            print(f"Avg OOS net_pct: {avg_net:.4f}")
            print(f"Avg OOS max_dd:  {avg_dd:.4f}")
            print(f"Avg OOS PF:      {avg_pf:.3f}")

        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            windows_df.to_csv(out, index=False)
            print(f"Wrote: {out}")

        if args.out_oos_equity:
            out2 = Path(args.out_oos_equity)
            out2.parent.mkdir(parents=True, exist_ok=True)
            oos_df.to_csv(out2, index=False)
            print(f"Wrote: {out2}")

        return 0

    # Sweep mode (single dataset optimization)
    if args.sweep:
        sweep_cfg = SweepConfig(
            mode=args.sweep_mode,
            max_evals=max(1, args.max_evals),
            cap_grid=(args.max_evals if args.cap_grid else None),
            seed=12345,
        )
        res = sweep(
            df=df,
            strategy_key=strat.key,
            grid_tokens=args.sweep,
            cfg=bt_cfg,
            objective_name=args.objective,
            sweep_cfg=sweep_cfg,
        )

        print(f"Sweep: {strat.name} ({strat.key}) mode={sweep_cfg.mode} objective={args.objective}")
        print(f"Evaluations: {len(res)}")
        if res.empty:
            print("No results.")
            return 0

        best = res.iloc[0].to_dict()
        print("\nTop result:")
        for k in ["objective_value","net_pct","max_drawdown_pct","profit_factor","win_rate","total_trades"]:
            print(f"  {k:18} {best.get(k)}")
        params = {k.replace("param_",""): v for k, v in best.items() if str(k).startswith("param_")}
        print("  params:", params)

        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            res.to_csv(out, index=False)
            print(f"\nWrote: {out}")
        return 0

    # Single run
    overrides = parse_kv_list(args.param, strat.params) if args.param else {}
    signals = strat.run(df, overrides)
    trades, curve = backtest(df, signals, bt_cfg)
    m = compute_metrics(bt_cfg.initial_equity, curve, trades)

    print(f"Strategy: {strat.name} ({strat.key})")
    if overrides:
        print(f"Params:   {overrides}")
    print(f"Trades:   {m.total_trades}")
    print(f"WinRate:  {m.win_rate*100:.2f}%")
    print(f"Net:      {m.net_pct*100:.2f}%")
    print(f"MaxDD:    {m.max_drawdown_pct*100:.2f}%")
    print(f"PF:       {m.profit_factor:.3f}" if m.profit_factor != float('inf') else "PF:       inf")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
