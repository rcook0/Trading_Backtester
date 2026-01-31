"""Trading Backtester — Streamlit UI (Commit 10)

Commit 10 focus: Interactive playback & execution fidelity
- Play/Pause at 1–30 bars/sec (deterministic cursor stepping)
- Keyboard is limited in Streamlit; buttons + auto-refresh implement playback
- Jump-to-time (nearest BarEvent time)
- Trade blotter + active position + unrealized PnL
- Still event-driven: UI replays engine-emitted events only

Foundation kept in mind:
- Slippage/latency/manual overlays will become *events* (no UI recompute)
"""

from __future__ import annotations

import io
import json
import tempfile
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from trading_backtester.catalog import list_strategies, get_strategy
from trading_backtester.data import load_csv_ohlcv
from trading_backtester.engine import BacktestConfig
from trading_backtester.params import ParamSpec
from trading_backtester.replay import EventStream

try:
    from trading_backtester.engine import backtest_with_events
    _HAS_EVENTS = True
except Exception:
    _HAS_EVENTS = False

st.set_page_config(page_title="Trading Backtester (Streamlit)", layout="wide")


# ------------------ helpers ------------------
def _param_widget(ps: ParamSpec):
    key = f"param__{ps.key}"
    if ps.type == "bool":
        return st.checkbox(ps.key, value=bool(ps.default), help=ps.help, key=key)
    if ps.type == "int":
        if ps.min is not None and ps.max is not None:
            return st.slider(ps.key, int(ps.min), int(ps.max), int(ps.default),
                             step=int(ps.step or 1), help=ps.help, key=key)
        return st.number_input(ps.key, value=int(ps.default), step=1, help=ps.help, key=key)
    if ps.type == "float":
        if ps.min is not None and ps.max is not None:
            step = float(ps.step or max((ps.max - ps.min) / 100.0, 0.0001))
            return st.slider(ps.key, float(ps.min), float(ps.max), float(ps.default),
                             step=step, help=ps.help, key=key)
        return st.number_input(ps.key, value=float(ps.default), step=float(ps.step or 0.0001), help=ps.help, key=key)
    return st.text_input(ps.key, value=str(ps.default), help=ps.help, key=key)


def _summary_metrics(equity: pd.DataFrame, closes: pd.DataFrame):
    if equity.empty:
        return
    initial = float(equity["equity"].iloc[0])
    last = float(equity["equity"].iloc[-1])
    net = (last / initial - 1.0) if initial else 0.0

    eq = equity["equity"].astype(float)
    peak = eq.cummax()
    dd = ((eq / peak) - 1.0).min() if len(eq) else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Equity", f"{last:,.2f}")
    c2.metric("Net %", f"{net*100:.2f}%")
    c3.metric("Max DD %", f"{dd*100:.2f}%")
    c4.metric("Closed trades", f"{len(closes)}")


def _latest_position_from_fills(fills: pd.DataFrame):
    # Reconstruct current position from fill actions (OPEN/REVERSE/CLOSE) — UI-only view.
    if fills.empty:
        return None
    side, entry, qty, t = None, None, None, None
    for _, r in fills.iterrows():
        action = str(r.get("action") or "")
        if action in ("OPEN", "REVERSE"):
            side = str(r.get("side") or "")
            entry = float(r.get("price"))
            qty = float(r.get("qty") or 0)
            t = r.get("time")
        elif action == "CLOSE":
            side, entry, qty, t = None, None, None, None
    if side is None:
        return None
    return {"side": side, "entry": entry, "qty": qty, "time": t}


def _unrealized_from_position(pos, last_close: float | None):
    if not pos or last_close is None:
        return None
    side = pos["side"]
    entry = float(pos["entry"])
    qty = float(pos["qty"])
    if entry == 0:
        return None
    dir_ = 1.0 if side == "BUY" else -1.0
    pnl = (last_close - entry) * dir_ * qty
    pct = (last_close / entry - 1.0) * dir_
    return {"pnl": pnl, "pct": pct, "last": last_close}


def _nearest_bar_index(events: list[dict[str, Any]], target: pd.Timestamp) -> int:
    # Find nearest BarEvent index in event list, then return that *event index*.
    best_i = 0
    best_dt = None
    for i, e in enumerate(events):
        if e.get("type") != "BarEvent":
            continue
        t = e.get("time")
        try:
            dt = pd.to_datetime(t)
        except Exception:
            continue
        if best_dt is None or abs((dt - target).total_seconds()) < abs((best_dt - target).total_seconds()):
            best_dt = dt
            best_i = i
    return best_i


def _charts(candles: pd.DataFrame, fills: pd.DataFrame, equity: pd.DataFrame, pos=None):
    left, right = st.columns([2, 1], gap="large")

    with left:
        if candles.empty:
            st.info("No BarEvent candles yet.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=candles["time"],
                open=candles["open"],
                high=candles["high"],
                low=candles["low"],
                close=candles["close"],
                name="OHLC"
            ))

            # Fill markers
            if not fills.empty:
                buys = fills[fills["side"] == "BUY"]
                sells = fills[fills["side"] == "SELL"]
                if not buys.empty:
                    fig.add_trace(go.Scatter(
                        x=buys["time"], y=buys["price"], mode="markers",
                        name="Fill BUY", marker=dict(symbol="triangle-up", size=10)
                    ))
                if not sells.empty:
                    fig.add_trace(go.Scatter(
                        x=sells["time"], y=sells["price"], mode="markers",
                        name="Fill SELL", marker=dict(symbol="triangle-down", size=10)
                    ))

            # Active position entry line (foundation for SL/TP lines later via events)
            if pos is not None and pos.get("entry") is not None:
                fig.add_hline(y=float(pos["entry"]), line_dash="dot")

            fig.update_layout(height=520, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)

    with right:
        if equity.empty:
            st.info("No EquityEvent curve yet.")
        else:
            efig = go.Figure()
            efig.add_trace(go.Scatter(x=equity["time"], y=equity["equity"], mode="lines", name="Equity"))
            efig.update_layout(height=520, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(efig, use_container_width=True)


# ------------------ main ------------------
def main():
    st.title("Trading Backtester — Streamlit UI (Commit 10)")

    if not _HAS_EVENTS:
        st.error("This build needs Commit 7+ engine with backtest_with_events().")
        st.stop()

    strategies = list_strategies()
    labels = [f"{s.key} — {s.name}" for s in strategies]
    map_label = {lbl: s for lbl, s in zip(labels, strategies)}

    with st.sidebar:
        st.header("Data")
        up = st.file_uploader("Upload OHLCV CSV (time,open,high,low,close,volume)", type=["csv"])

        st.header("Strategy")
        choice = st.selectbox("Strategy", labels, index=0)
        strat = get_strategy(map_label[choice].key)
        st.caption(strat.description)

        st.subheader("Parameters")
        overrides = {}
        for ps in strat.params:
            overrides[ps.key] = _param_widget(ps)

        st.header("Execution")
        sl = st.number_input("SL %", value=1.0, min_value=0.0, step=0.1) / 100.0
        tp = st.number_input("TP %", value=2.0, min_value=0.0, step=0.1) / 100.0
        trail = st.number_input("Trail %", value=0.0, min_value=0.0, step=0.1) / 100.0
        risk = st.number_input("Risk per trade %", value=1.0, min_value=0.0, step=0.1) / 100.0


        entry_slip = st.number_input("Entry slippage (bps)", value=0.0, min_value=0.0, step=0.1) 
        exit_slip  = st.number_input("Exit slippage (bps)", value=0.0, min_value=0.0, step=0.1)
        entry_lat  = st.number_input("Entry latency (bars)", value=0, min_value=0, step=1)
        exit_lat   = st.number_input("Exit latency (bars)", value=0, min_value=0, step=1)
        run = st.button("Run backtest", type="primary")
        st.divider()

        st.header("Playback")
        # Commit 10: playback with auto-refresh.
        if "playing" not in st.session_state:
            st.session_state["playing"] = False
        speed = st.slider("Speed (bars/sec)", 1, 30, 10, help="Deterministic: each tick advances cursor by this many bars.")
        step_n = st.number_input("Step bars", value=1, min_value=1, max_value=5000)
        ff_n = st.number_input("Fast-forward bars", value=50, min_value=1, max_value=50000)

        colA, colB = st.columns(2)
        with colA:
            play_pause = st.button("Play/Pause", type="secondary")
        with colB:
            to_end = st.button("To end")

        step_btn = st.button("Step")
        ff_btn = st.button("Fast-forward")

        st.divider()
        st.header("Jump")
        jump_txt = st.text_input("Jump to time (ISO, e.g. 2019-10-01T00:00:00)", value="")
        jump_btn = st.button("Jump")

    if up is None:
        st.info("Upload a CSV to begin.")
        return

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(up.getvalue())
        path = tmp.name

    df = load_csv_ohlcv(path)

    if "events" not in st.session_state:
        st.session_state["events"] = []
    if "stream" not in st.session_state:
        st.session_state["stream"] = None

    if run:
        cfg = BacktestConfig(
            risk_per_trade=float(risk),
            stop_loss_pct=float(sl),
            take_profit_pct=float(tp),
            trailing_pct=float(trail),
            entry_slippage_bps=float(entry_slip),
            exit_slippage_bps=float(exit_slip),
            entry_latency_bars=int(entry_lat),
            exit_latency_bars=int(exit_lat),
        )
        signals = strat.run(df, overrides)
        trades, curve, events = backtest_with_events(df, signals, cfg, emit_events=True)

        st.session_state["events"] = events
        st.session_state["stream"] = EventStream(events)
        st.session_state["stream"].seek(0)
        st.session_state["playing"] = False

        buf = io.StringIO()
        for e in events:
            buf.write(json.dumps(e, default=str) + "\n")
        st.download_button("Download events.jsonl", data=buf.getvalue(), file_name="events.jsonl", mime="application/jsonl")

    stream: EventStream | None = st.session_state.get("stream")
    if stream is None:
        st.warning("Run a backtest to generate the event stream.")
        return

    # playback triggers
    if play_pause:
        st.session_state["playing"] = not bool(st.session_state["playing"])

    if step_btn:
        stream.step(int(step_n))
        st.session_state["playing"] = False

    if ff_btn:
        stream.step(int(ff_n))
        st.session_state["playing"] = False

    if to_end:
        stream.seek(stream.max_index)
        st.session_state["playing"] = False

    if jump_btn and jump_txt.strip():
        try:
            target = pd.to_datetime(jump_txt.strip())
            i = _nearest_bar_index(st.session_state["events"], target)
            stream.seek(i)
            st.session_state["playing"] = False
        except Exception as e:
            st.sidebar.error(f"Jump parse failed: {e}")

    # slider seek
    idx = st.slider("Replay cursor", 0, stream.max_index, stream.cursor.index)
    if idx != stream.cursor.index:
        stream.seek(idx)
        st.session_state["playing"] = False

    # auto-advance when playing: 1 Hz tick, deterministic step
    if st.session_state.get("playing"):
        st.caption(f"▶ Playing at {speed} bars/sec")
        st.autorefresh(interval=1000, key="play_tick")
        stream.step(int(speed))

    candles = stream.candles_upto()
    equity = stream.equity_upto()
    fills = stream.fills_upto()
    closes = stream.trade_closes_upto()

    pos = _latest_position_from_fills(fills)
    last_close = float(candles["close"].iloc[-1]) if not candles.empty else None
    unr = _unrealized_from_position(pos, last_close)

    _summary_metrics(equity, closes)

    # state badges
    s1, s2, s3 = st.columns(3)
    s1.write(f"**Time:** {stream.current_time() or '—'}")
    s2.write(f"**Position:** {'FLAT' if not pos else f"{pos['side']} qty={pos['qty']:.2f} entry={pos['entry']:.2f}"}")
    s3.write(f"**Unrealized:** {'—' if not unr else f"{unr['pnl']:.2f} ({unr['pct']*100:.2f}%)"}")

    _charts(candles, fills, equity, pos=pos)

    with st.expander("Trade blotter (closed trades)"):
        if closes.empty:
            st.write("No closed trades yet.")
        else:
            st.dataframe(closes, use_container_width=True)

    with st.expander("Event log (tail)"):
        head = stream.head(True)
        st.write(f"Events: {len(stream.events)} | Cursor: {stream.cursor.index}/{stream.max_index} | Time: {stream.current_time()}")
        st.json(head[-25:] if len(head) > 25 else head)


if __name__ == "__main__":
    main()
