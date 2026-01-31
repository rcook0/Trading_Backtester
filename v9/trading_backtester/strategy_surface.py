from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
import importlib
import inspect
import pandas as pd

from .params import ParamSpec, merge_params

Side = str  # "BUY" | "SELL"

def _to_legacy_df(df: pd.DataFrame) -> pd.DataFrame:
    # normalized: time, open, high, low, close, volume
    # legacy strategies expect: Date, Open, High, Low, Close, Volume
    out = df.copy()
    rename = {
        "time": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
    cols = {c: rename[c] for c in rename if c in out.columns}
    out = out.rename(columns=cols)
    if "Date" in out.columns:
        out["Date"] = pd.to_datetime(out["Date"], utc=False)  # keep tz if any
    return out

def _map_side(s: str) -> Side:
    s2 = (s or "").strip().upper()
    if s2 in ("LONG","BUY"):
        return "BUY"
    if s2 in ("SHORT","SELL"):
        return "SELL"
    raise ValueError(f"Unknown side '{s}' in strategy output")

@dataclass(frozen=True)
class StrategySurface:
    key: str
    name: str
    description: str
    module: str
    cls: str
    params: list[ParamSpec]

    def run(self, df_norm: pd.DataFrame, overrides: dict[str, Any] | None = None) -> list[tuple]:
        """Run strategy on normalized df and return signals [(time, BUY/SELL, price)]."""
        df_leg = _to_legacy_df(df_norm)
        params = merge_params(overrides or {}, self.params)

        mod = importlib.import_module(self.module)
        klass = getattr(mod, self.cls)

        # Strategy constructors in your Commit 2 bundle generally look like: __init__(df, **params)
        sig = inspect.signature(klass.__init__)
        kwargs = {k: v for k, v in params.items() if k in sig.parameters}
        inst = klass(df_leg, **kwargs)
        trades = inst.run()

        out = []
        for t, side, price in trades:
            out.append((t, _map_side(side), float(price)))
        return out
