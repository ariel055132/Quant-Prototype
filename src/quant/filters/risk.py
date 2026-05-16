"""Risk and liquidity filters for candidate eligibility."""

from __future__ import annotations

import pandas as pd

from quant.config import QuantConfig


def apply_filters(factors: pd.DataFrame, config: QuantConfig) -> pd.DataFrame:
    """Attach explicit pass/fail flags and eligibility state."""
    frame = factors.copy()
    frame["factor_pass"] = frame["momentum_score"].notna()
    frame["volatility_pass"] = frame["volatility_20d"].le(config.volatility_threshold)
    frame["liquidity_pass"] = frame["avg_volume_20d"].ge(config.min_avg_volume)
    frame["eligible"] = frame[["factor_pass", "volatility_pass", "liquidity_pass"]].all(axis=1)
    return frame
