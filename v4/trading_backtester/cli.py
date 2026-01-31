from __future__ import annotations

import argparse
from .catalog import list_strategies, get_strategy
from .data import load_csv_ohlcv
from .engine import BacktestConfig, backtest
from .metrics import compute_metrics
from .params import parse_kv_list

def main(argv=None):
    ap = argparse.ArgumentParser(prog="trading_backtester")
    ap.add_argument("--list", action="store_true", help="List available strategies")
    ap.add_argument("--describe", default=None, help="Print description + params for a strategy key/name")
    ap.add_argument("--strategy", default="sigma_extreme", help="Strategy key or name")
    ap.add_argument("--param", action="append", default=[], help="Override strategy param: key=value (repeatable)")

    ap.add_argument("--csv", default=None, help="Path to OHLCV CSV (time,open,high,low,close,volume)")
    ap.add_argument("--sl", type=float, default=0.01, help="Stop loss pct (0.01=1%)")
    ap.add_argument("--tp", type=float, default=0.02, help="Take profit pct")
    ap.add_argument("--trail", type=float, default=0.0, help="Trailing pct (0 disables)")
    ap.add_argument("--risk", type=float, default=0.01, help="Risk per trade fraction of equity")
    args = ap.parse_args(argv)

    if args.list:
        for s in list_strategies():
            print(f"{s.key:28}  {s.name}")
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
            print(f"  - {p.key} ({p.type}) default={p.default}{rng}  {p.help}")
        return 0

    if not args.csv:
        raise SystemExit("--csv is required.")

    df = load_csv_ohlcv(args.csv)
    strat = get_strategy(args.strategy)

    overrides = parse_kv_list(args.param, strat.params) if args.param else {}
    signals = strat.run(df, overrides)

    cfg = BacktestConfig(risk_per_trade=args.risk, stop_loss_pct=args.sl, take_profit_pct=args.tp, trailing_pct=args.trail)
    trades, curve = backtest(df, signals, cfg)
    m = compute_metrics(cfg.initial_equity, curve, trades)

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
