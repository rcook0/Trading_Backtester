from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pandas as pd

@dataclass(frozen=True)
class CsvSpec:
    time: str = "time"
    open: str = "open"
    high: str = "high"
    low: str = "low"
    close: str = "close"
    volume: str = "volume"
    tz: str | None = "UTC"  # parse/convert to this timezone (None keeps naive)

def load_csv_ohlcv(path: str | Path, spec: CsvSpec = CsvSpec(), sep: str = ",") -> pd.DataFrame:
    """Load OHLCV CSV into a normalized DataFrame.

    Required columns: time, open, high, low, close (case-insensitive by rename).
    Optional: volume.
    Output columns: ['time','open','high','low','close','volume'] and sorted by time.
    """
    path = Path(path)
    df = pd.read_csv(path, sep=sep)
    cols = {c.lower(): c for c in df.columns}
    def col(name: str) -> str:
        key = name.lower()
        if key not in cols:
            raise ValueError(f"Missing column '{name}' in CSV. Present: {list(df.columns)}")
        return cols[key]

    rename = {
        col(spec.time): "time",
        col(spec.open): "open",
        col(spec.high): "high",
        col(spec.low): "low",
        col(spec.close): "close",
    }
    if spec.volume.lower() in cols:
        rename[cols[spec.volume.lower()]] = "volume"
    df = df.rename(columns=rename)

    df["time"] = pd.to_datetime(df["time"], utc=True, errors="raise")
    if spec.tz is None:
        df["time"] = df["time"].dt.tz_convert(None)
    else:
        df["time"] = df["time"].dt.tz_convert(spec.tz)

    if "volume" not in df.columns:
        df["volume"] = 0.0

    df = df[["time","open","high","low","close","volume"]].copy()
    df = df.sort_values("time").reset_index(drop=True)
    return df
