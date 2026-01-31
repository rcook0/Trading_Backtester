from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Literal, Optional
import json

class EventBase:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)  # type: ignore[arg-type]

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

# Concrete event types (time is first to keep dataclass field ordering sane)

@dataclass(frozen=True)
class BarEvent(EventBase):
    time: Any
    type: Literal["bar"] = "bar"
    index: int = 0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: Optional[float] = None

@dataclass(frozen=True)
class SignalEvent(EventBase):
    time: Any
    type: Literal["signal"] = "signal"
    side: Literal["BUY","SELL"] = "BUY"
    price: float = 0.0
    source: str = "strategy"

@dataclass(frozen=True)
class FillEvent(EventBase):
    time: Any
    type: Literal["fill"] = "fill"
    action: Literal["OPEN","CLOSE","REVERSE"] = "OPEN"
    side: Literal["BUY","SELL"] | None = None

    # Executed price used by PnL. (Back-compat: UIs read `price`.)
    price: float = 0.0

    # Optional execution-fidelity fields (Commit 11)
    intended_price: Optional[float] = None      # pre-slippage target
    slippage_bps: float = 0.0                   # basis points applied to intended/base
    latency_bars: int = 0                       # bars delayed before fill
    submitted_time: Optional[Any] = None        # when the order was "submitted"/triggered

    qty: float = 0.0
    reason: str = ""

@dataclass(frozen=True)
class EquityEvent(EventBase):
    time: Any
    type: Literal["equity"] = "equity"
    equity: float = 0.0

@dataclass(frozen=True)
class TradeClosedEvent(EventBase):
    time: Any
    type: Literal["trade_closed"] = "trade_closed"
    side: Literal["BUY","SELL"] = "BUY"
    entry_price: float = 0.0
    exit_price: float = 0.0
    qty: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    reason: str = ""

# -------- Wire contract (for JSONL + cross-UI compatibility) --------
# Wire event shape:
#   { "time": <iso>, "type": "<ClassName>", "payload": { ...fields without time/type... } }

def to_wire(ev: EventBase) -> dict[str, Any]:
    d = ev.to_dict()
    t = d.pop("time", None)
    d.pop("type", None)
    return {"time": t, "type": ev.__class__.__name__, "payload": d}

def dump_events_jsonl_wire(events: list[EventBase], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(to_wire(ev), default=str) + "\n")
