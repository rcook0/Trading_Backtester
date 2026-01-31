from __future__ import annotations

import argparse
from .catalog import list_strategies, get_strategy
from .data import load_csv_ohlcv
from .engine import BacktestConfig, backtest
from .metrics import compute_metrics

def main(argv=None):
    ap = argparse.ArgumentParser(prog="trading_backtester")
    ap.add_argument("--list", action="store_true", help="List available strategies")
    ap.add_argument("--strategy", default="sigma_extreme", help="Strategy key or name")
    ap.add_argument("--csv", default=None, help="Path to OHLCV CSV (time,open,high,low,close,volume)")
    ap.add_argument("--sl", type=float, default=0.01, help="Stop loss pct (e.g. 0.01=1%)")
    ap.add_argument("--tp", type=float, default=0.02, help="Take profit pct")
    ap.add_argument("--trail", type=float, default=0.0, help="Trailing pct (0 disables)")
    ap.add_argument("--risk", type=float, default=0.01, help="Risk per trade fraction of equity")
    args = ap.parse_args(argv)

    if args.list:
        for s in list_strategies():
            print(f"{s.key:28}  {s.name}")
        return 0

    if not args.csv:
        raise SystemExit("--csv is required (commit 3 adds a real engine; provide data)." )

    df = load_csv_ohlcv(args.csv)
    strat = get_strategy(args.strategy)

    signals = strat.run(df)  # strategy-specific params remain inside each strategy for now
    cfg = BacktestConfig(risk_per_trade=args.risk, stop_loss_pct=args.sl, take_profit_pct=args.tp, trailing_pct=args.trail)

    trades, curve = backtest(df, signals, cfg)
    m = compute_metrics(cfg.initial_equity, curve, trades)

    print(f"Strategy: {args.strategy}")
    print(f"Trades:   {m.total_trades}")
    print(f"WinRate:  {m.win_rate*100:.2f}%")
    print(f"Net:      {m.net_pct*100:.2f}%")
    print(f"MaxDD:    {m.max_drawdown_pct*100:.2f}%")
    print(f"PF:       {m.profit_factor:.3f}" if m.profit_factor != float('inf') else "PF:       inf")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
