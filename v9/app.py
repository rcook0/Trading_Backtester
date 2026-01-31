"""Trading Backtester — Streamlit UI (Commit 8)

Event-driven UI:
- Run => engine emits formal events (Commit 7)
- Replay => UI replays events via EventStream (Commit 8)

The UI does *not* compute strategy logic or fills.
"""

from __future__ import annotations

import io
import json
import tempfile

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

def _charts(candles: pd.DataFrame, fills: pd.DataFrame, equity: pd.DataFrame):
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

def main():
    st.title("Trading Backtester — Streamlit UI (Commit 8)")

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

        run = st.button("Run backtest", type="primary")
        st.divider()

        st.header("Replay")
        step_n = st.number_input("Step bars", value=1, min_value=1, max_value=5000)
        ff_n = st.number_input("Fast-forward bars", value=50, min_value=1, max_value=50000)

        step_btn = st.button("Step")
        ff_btn = st.button("Fast-forward")
        end_btn = st.button("To end")

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
        )
        signals = strat.run(df, overrides)
        trades, curve, events = backtest_with_events(df, signals, cfg, emit_events=True)
        st.session_state["events"] = events
        st.session_state["stream"] = EventStream(events)
        st.session_state["stream"].seek(0)

        buf = io.StringIO()
        for e in events:
            buf.write(json.dumps(e, default=str) + "\n")
        st.download_button("Download events.jsonl", data=buf.getvalue(), file_name="events.jsonl", mime="application/jsonl")

    stream: EventStream | None = st.session_state.get("stream")
    if stream is None:
        st.warning("Run a backtest to generate the event stream.")
        return

    if step_btn:
        stream.step(int(step_n))
    if ff_btn:
        stream.step(int(ff_n))
    if end_btn:
        stream.seek(stream.max_index)

    idx = st.slider("Replay cursor", 0, stream.max_index, stream.cursor.index)
    if idx != stream.cursor.index:
        stream.seek(idx)

    candles = stream.candles_upto()
    equity = stream.equity_upto()
    fills = stream.fills_upto()
    closes = stream.trade_closes_upto()

    _summary_metrics(equity, closes)
    _charts(candles, fills, equity)

    with st.expander("Event log (tail)"):
        head = stream.head(True)
        st.write(f"Events: {len(stream.events)} | Cursor: {stream.cursor.index}/{stream.max_index} | Time: {stream.current_time()}")
        st.json(head[-25:] if len(head) > 25 else head)

    with st.expander("Closed trades"):
        if closes.empty:
            st.write("No closed trades yet.")
        else:
            st.dataframe(closes, use_container_width=True)

if __name__ == "__main__":
    main()
