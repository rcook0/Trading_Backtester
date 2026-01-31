from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any
import importlib

@dataclass(frozen=True)
class StrategyInfo:
    key: str
    name: str
    module: str
    cls: str
    description: str

_STRATEGIES: list[StrategyInfo] = [
    StrategyInfo("sigma_extreme", "Sigma Extreme", "strategies.sigma_extreme", "SigmaExtreme", "Z-score of returns; fade extremes."),
    StrategyInfo("opening_range_breakout", "Opening Range Breakout", "strategies.opening_range_breakout", "OpeningRangeBreakout", "Range breakout after session open."),
    StrategyInfo("gap_fade", "Gap Fade / Continuation", "strategies.gap_fade", "GapFade", "Large gaps fade (or follow), small gaps follow."),
    StrategyInfo("time_of_day_mean_reversion", "Time-of-Day Mean Reversion", "strategies.time_of_day_mean_reversion", "TimeOfDayMeanReversion", "At a time-of-day, fade z-score extremes."),
    StrategyInfo("microstructure_imbalance", "Microstructure Imbalance", "strategies.microstructure_imbalance", "MicrostructureImbalance", "Signed volume proxy; trade imbalance extremes."),
    StrategyInfo("mean_reversion_on_returns", "Mean-Reversion on Returns", "strategies.mean_reversion_on_returns", "MeanReversionOnReturns", "Z-score of returns; fade extremes."),
    StrategyInfo("probabilistic_time_of_day_edge", "Probabilistic Time-of-Day Edge", "strategies.probabilistic_time_of_day_edge", "ProbabilisticTimeOfDayEdge", "Rolling probability edge at a time-of-day."),
    StrategyInfo("overnight_gap", "Overnight Gap", "strategies.overnight_gap", "OvernightGap", "Trade direction of large open-close gaps."),
    StrategyInfo("probability_of_sign_sequences", "Probability of Sign Sequences", "strategies.probability_of_sign_sequences", "ProbabilityOfSignSequences", "Run-length reversal after N same-direction closes."),
    StrategyInfo("return_clustering", "Return Clustering (GARCH-like)", "strategies.return_clustering", "ReturnClustering", "High variance regimes; drift-follow."),
    StrategyInfo("extreme_quantile", "Extreme Quantile", "strategies.extreme_quantile", "ExtremeQuantile", "Empirical quantile filter on returns."),
    StrategyInfo("expected_value_maximization", "Expected Value Maximization", "strategies.expected_value_maximization", "ExpectedValueMaximization", "Trade when rolling mean return exceeds threshold."),
    StrategyInfo("sequential_reversal", "Sequential Reversal", "strategies.sequential_reversal", "SequentialReversal", "After N consecutive bars, enter reversal."),
    StrategyInfo("monte_carlo_bootstrap", "Monte Carlo / Bootstrapping", "strategies.monte_carlo_bootstrap", "MonteCarloBootstrap", "Bootstrap sign of returns to estimate p(up)."),
    StrategyInfo("volatility_breakout", "Volatility Breakout", "strategies.volatility_breakout", "VolatilityBreakout", "Continuation on extreme moves."),
    StrategyInfo("mean_reversion_on_price_changes", "Mean Reversion on Price Changes", "strategies.mean_reversion_on_price_changes", "MeanReversionOnPriceChanges", "Z-score on deltas; fade extremes."),
    StrategyInfo("custom_placeholder", "Custom Placeholder", "strategies.custom_placeholder", "CustomPlaceholder", "Template stub: add your own strategy here."),
]

def list_strategies() -> list[StrategyInfo]:
    return list(_STRATEGIES)

def get_strategy(key_or_name: str):
    """Return instantiated strategy by key or name."""
    needle = key_or_name.strip().lower()
    info = next((s for s in _STRATEGIES if s.key == needle or s.name.lower() == needle), None)
    if info is None:
        raise KeyError(f"Unknown strategy '{key_or_name}'. Use list_strategies().")

    mod = importlib.import_module(info.module)
    cls = getattr(mod, info.cls)
    return cls()
