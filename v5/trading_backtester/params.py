from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ParamType = Literal["int","float","bool","str"]

@dataclass(frozen=True)
class ParamSpec:
    key: str
    type: ParamType
    default: Any
    label: str = ""
    help: str = ""
    min: float | None = None
    max: float | None = None
    step: float | None = None

def coerce(value: str, typ: ParamType) -> Any:
    v = value.strip()
    if typ == "int":
        return int(float(v))
    if typ == "float":
        return float(v)
    if typ == "bool":
        if v.lower() in ("1","true","t","yes","y","on"):
            return True
        if v.lower() in ("0","false","f","no","n","off"):
            return False
        raise ValueError(f"Cannot coerce '{value}' to bool")
    return v

def parse_kv_list(kvs: list[str], schema: list[ParamSpec]) -> dict[str, Any]:
    specs = {s.key: s for s in schema}
    out: dict[str, Any] = {}
    for kv in kvs:
        if "=" not in kv:
            raise ValueError(f"Bad param '{kv}'. Use key=value")
        k, v = kv.split("=", 1)
        k = k.strip()
        if k not in specs:
            raise KeyError(f"Unknown param '{k}'. Known: {sorted(specs.keys())}")
        out[k] = coerce(v, specs[k].type)
    return out

def merge_params(overrides: dict[str, Any], schema: list[ParamSpec]) -> dict[str, Any]:
    params = {s.key: s.default for s in schema}
    params.update(overrides or {})
    # basic validation
    for s in schema:
        if s.key not in params:
            params[s.key] = s.default
        v = params[s.key]
        if s.type in ("int","float") and isinstance(v, (int,float)):
            if s.min is not None and v < s.min: raise ValueError(f"{s.key} < min ({v} < {s.min})")
            if s.max is not None and v > s.max: raise ValueError(f"{s.key} > max ({v} > {s.max})")
    return params
