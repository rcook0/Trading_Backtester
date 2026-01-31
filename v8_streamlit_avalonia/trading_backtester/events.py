from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Literal
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
    volume: float | None = None

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
    price: float = 0.0
    size: float = 0.0
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
    size: float = 0.0
    pnl: float = 0.0
    reason: str = ""
