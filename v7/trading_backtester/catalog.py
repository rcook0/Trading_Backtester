from __future__ import annotations

from .params import ParamSpec
from .strategy_surface import StrategySurface

_STRATEGIES: list[StrategySurface] = [
    StrategySurface(
        key="sigma_extreme",
        name="Sigma Extreme",
        description="Z-score extremes on rolling mean/std; fade extremes (contrarian).",
        module="strategies.sigma_extreme",
        cls="SigmaExtreme",
        params=[
            ParamSpec("window","int",20,label="Window",help="Rolling window (bars)",min=2,max=5000,step=1),
            ParamSpec("sigma","float",2.0,label="Sigma",help="Std-dev multiple",min=0.1,max=10,step=0.1),
        ],
    ),
    StrategySurface(
        key="opening_range_breakout",
        name="Opening Range Breakout",
        description="Use first N bars of the day as opening range; trade first breakout beyond high/low.",
        module="strategies.opening_range_breakout",
        cls="OpeningRangeBreakout",
        params=[
            ParamSpec("minutes","int",30,label="Bars",help="Number of bars in opening range (interpreted as bars, not clock-minutes).",min=1,max=2000,step=1),
        ],
    ),
    StrategySurface(
        key="gap_fade",
        name="Gap Fade / Continuation",
        description="Trade gaps between previous close and today open; fade or follow depending on threshold.",
        module="strategies.gap_fade",
        cls="GapFade",
        params=[
            ParamSpec("gap_threshold","float",0.004,label="Gap threshold",help="Absolute gap threshold as fraction (0.004=0.4%).",min=0.0001,max=0.2,step=0.0001),
            ParamSpec("fade_extremes","bool",True,label="Fade extremes",help="If true, fade big gaps; otherwise follow.",),
        ],
    ),
    StrategySurface(
        key="time_of_day_mean_reversion",
        name="Time-of-Day Mean Reversion",
        description="At a specific time-of-day, compare price to rolling mean/std and fade extremes.",
        module="strategies.time_of_day_mean_reversion",
        cls="TimeOfDayMeanReversion",
        params=[
            ParamSpec("hour","int",12,label="Hour",help="Hour (0-23) in dataframe timezone.",min=0,max=23,step=1),
            ParamSpec("minute","int",0,label="Minute",help="Minute (0-59).",min=0,max=59,step=1),
            ParamSpec("window","int",200,label="Window",help="Rolling window (bars).",min=5,max=20000,step=1),
            ParamSpec("k","float",1.5,label="Z threshold",help="Z-score threshold to trigger fade.",min=0.1,max=10,step=0.1),
        ],
    ),
    StrategySurface(
        key="microstructure_imbalance",
        name="Microstructure Imbalance",
        description="Proxy order-flow imbalance using candle-direction signed volume; trade when imbalance is extreme.",
        module="strategies.microstructure_imbalance",
        cls="MicrostructureImbalance",
        params=[
            ParamSpec("window","int",50,label="Window",help="Rolling bars for imbalance estimate.",min=2,max=20000,step=1),
            ParamSpec("threshold","float",0.6,label="Threshold",help="Imbalance ratio threshold (0-1).",min=0.05,max=0.99,step=0.01),
        ],
    ),
    StrategySurface(
    key="mean_reversion_returns",
    name="Mean Reversion on Returns",
    description="Contrarian: when the recent average return is positive and the current return flips negative (or vice versa), fade it.",
    module="strategies.mean_reversion_returns",
    cls="MeanReversionReturns",
    params=[
        ParamSpec("lookback","int",5,label="Lookback",help="Number of prior bars used to compute average return.",min=2,max=5000,step=1),
    ],
),

    StrategySurface(
    key="probabilistic_time_edge",
    name="Probabilistic Time-of-Day Edge",
    description="At a chosen hour, take the average directional drift seen at that hour historically (toy baseline).",
    module="strategies.probabilistic_time_edge",
    cls="ProbabilisticTimeEdge",
    params=[
        ParamSpec("hour","int",10,label="Hour",help="Hour (0-23) in dataframe timezone.",min=0,max=23,step=1),
    ],
),

    StrategySurface(
        key="overnight_gap",
        name="Overnight Gap",
        description="Trade direction of gaps when open differs materially from prior close.",
        module="strategies.overnight_gap",
        cls="OvernightGap",
        params=[
            ParamSpec("min_gap","float",0.002,label="Min gap",help="Minimum absolute gap as fraction (0.002=0.2%).",min=0.0001,max=0.2,step=0.0001),
        ],
    ),
    StrategySurface(
        key="sign_sequence_prob",
        name="Probability of Sign Sequences",
        description="Run-length reversal after N consecutive up/down closes.",
        module="strategies.sign_sequence_prob",
        cls="SignSequenceProb",
        params=[
            ParamSpec("run_length","int",5,label="Run length",help="Number of consecutive closes in one direction.",min=2,max=200,step=1),
        ],
    ),
    StrategySurface(
        key="return_clustering",
        name="Return Clustering (GARCH-like)",
        description="Detect high-variance regimes via rolling variance; trade in direction of drift when variance is high.",
        module="strategies.return_clustering",
        cls="ReturnClustering",
        params=[
            ParamSpec("window","int",100,label="Window",help="Rolling window.",min=5,max=20000,step=1),
            ParamSpec("var_mult","float",2.0,label="Variance multiple",help="Trigger when variance exceeds baseline * var_mult.",min=0.5,max=20,step=0.1),
        ],
    ),
    StrategySurface(
        key="extreme_quantile",
        name="Extreme Quantile",
        description="Empirical quantile filter on returns: long below qLow, short above qHigh.",
        module="strategies.extreme_quantile",
        cls="ExtremeQuantile",
        params=[
            ParamSpec("window","int",250,label="Window",help="Rolling window.",min=20,max=50000,step=1),
            ParamSpec("q_low","float",0.05,label="Low quantile",help="Lower quantile.",min=0.001,max=0.2,step=0.001),
            ParamSpec("q_high","float",0.95,label="High quantile",help="Upper quantile.",min=0.8,max=0.999,step=0.001),
        ],
    ),
    StrategySurface(
    key="expected_value",
    name="Expected Value Threshold",
    description="Trade when the single-bar return exceeds a positive/negative threshold.",
    module="strategies.expected_value",
    cls="ExpectedValue",
    params=[
        ParamSpec("threshold","float",0.0005,label="Threshold",help="Return threshold (0.0005=0.05%).",min=0.0,max=0.05,step=0.0001),
    ],
),

    StrategySurface(
        key="sequential_reversal",
        name="Sequential Reversal",
        description="After N consecutive bars in one direction, enter reversal.",
        module="strategies.sequential_reversal",
        cls="SequentialReversal",
        params=[
            ParamSpec("n","int",6,label="Run length",help="Consecutive bars threshold.",min=2,max=500,step=1),
        ],
    ),
    StrategySurface(
        key="monte_carlo_bootstrap",
        name="Monte Carlo / Bootstrapping",
        description="Bootstrap recent return signs to estimate P(up); trade if P(up) or P(down) exceeds threshold.",
        module="strategies.monte_carlo_bootstrap",
        cls="MonteCarloBootstrap",
        params=[
            ParamSpec("window","int",200,label="Window",help="Window of bars to sample from.",min=20,max=50000,step=1),
            ParamSpec("samples","int",200,label="Samples",help="Bootstrap samples.",min=20,max=5000,step=1),
            ParamSpec("min_p","float",0.6,label="Min prob",help="Minimum probability edge.",min=0.51,max=0.99,step=0.01),
            ParamSpec("seed","int",12345,label="Seed",help="RNG seed for reproducibility.",min=0,max=2_000_000_000,step=1),
        ],
    ),
    StrategySurface(
        key="volatility_breakout",
        name="Volatility Breakout",
        description="ATR-like range average; trade continuation when current range exceeds k * average range.",
        module="strategies.volatility_breakout",
        cls="VolatilityBreakout",
        params=[
            ParamSpec("lookback","int",20,label="Lookback",help="Range average lookback.",min=2,max=20000,step=1),
            ParamSpec("k","float",0.5,label="k",help="Multiplier above average range to trigger.",min=0.05,max=10,step=0.05),
        ],
    ),
    StrategySurface(
        key="mean_reversion_price_changes",
        name="Mean Reversion on Price Changes",
        description="Z-score of raw price deltas; fade extremes.",
        module="strategies.mean_reversion_price_changes",
        cls="MeanReversionOnPriceChanges",
        params=[
            ParamSpec("window","int",100,label="Window",help="Rolling window.",min=5,max=20000,step=1),
            ParamSpec("k","float",2.0,label="Z threshold",help="Z-score threshold.",min=0.1,max=10,step=0.1),
        ],
    ),
]

def list_strategies():
    return list(_STRATEGIES)

def get_strategy(key_or_name: str) -> StrategySurface:
    needle = key_or_name.strip().lower()
    s = next((x for x in _STRATEGIES if x.key == needle or x.name.lower() == needle), None)
    if not s:
        raise KeyError(f"Unknown strategy '{key_or_name}'. Use --list.")
    return s
