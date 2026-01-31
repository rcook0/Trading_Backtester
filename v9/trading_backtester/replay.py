from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json
import pandas as pd

Event = dict[str, Any]

def load_events_jsonl(path: str) -> list[Event]:
    events: list[Event] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events

def dump_events_jsonl(events: list[Event], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, default=str) + "\n")

@dataclass
class ReplayCursor:
    index: int = 0

class EventStream:
    """Deterministic event stream replayer.

    UI rule:
      - the UI never computes trades/metrics
      - it only replays this stream and renders derived views (candles/equity/fills).
    """

    def __init__(self, events: list[Event]):
        self.events = events or []
        self.cursor = ReplayCursor(index=0)

    @property
    def max_index(self) -> int:
        return max(0, len(self.events) - 1)

    def seek(self, index: int) -> None:
        if not self.events:
            self.cursor.index = 0
            return
        self.cursor.index = max(0, min(int(index), self.max_index))

    def step(self, n: int = 1) -> None:
        self.seek(self.cursor.index + int(n))

    def head(self, inclusive: bool = True) -> list[Event]:
        if not self.events:
            return []
        i = self.cursor.index
        return self.events[: (i + 1 if inclusive else i)]

    def current_time(self) -> str | None:
        if not self.events:
            return None
        return self.events[self.cursor.index].get("time")

    # ---- materialized views for UIs ----
    def candles_upto(self) -> pd.DataFrame:
        rows = []
        for e in self.head(True):
            if e.get("type") == "BarEvent":
                p = e.get("payload", {})
                rows.append({
                    "time": pd.to_datetime(e.get("time")),
                    "open": float(p.get("open")),
                    "high": float(p.get("high")),
                    "low": float(p.get("low")),
                    "close": float(p.get("close")),
                    "volume": float(p.get("volume", 0) or 0),
                })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("time").reset_index(drop=True)
        return df

    def equity_upto(self) -> pd.DataFrame:
        rows = []
        for e in self.head(True):
            if e.get("type") == "EquityEvent":
                p = e.get("payload", {})
                rows.append({
                    "time": pd.to_datetime(e.get("time")),
                    "equity": float(p.get("equity")),
                })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("time").reset_index(drop=True)
        return df

    def fills_upto(self) -> pd.DataFrame:
        rows = []
        for e in self.head(True):
            if e.get("type") == "FillEvent":
                p = e.get("payload", {})
                rows.append({
                    "time": pd.to_datetime(e.get("time")),
                    "action": p.get("action"),
                    "side": p.get("side"),
                    "price": float(p.get("price")),
                    "qty": float(p.get("qty", 0) or 0),
                    "reason": p.get("reason"),
                })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("time").reset_index(drop=True)
        return df

    def trade_closes_upto(self) -> pd.DataFrame:
        rows = []
        for e in self.head(True):
            if e.get("type") == "TradeClosedEvent":
                p = e.get("payload", {})
                rows.append({
                    "time": pd.to_datetime(e.get("time")),
                    "side": p.get("side"),
                    "entry_price": float(p.get("entry_price")),
                    "exit_price": float(p.get("exit_price")),
                    "pnl": float(p.get("pnl")),
                    "pnl_pct": float(p.get("pnl_pct")),
                    "reason": p.get("reason"),
                })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("time").reset_index(drop=True)
        return df
