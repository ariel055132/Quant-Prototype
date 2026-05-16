"""Risk and liquidity filters for candidate eligibility."""

# File role: apply pass/fail eligibility rules for strategy selection.

from __future__ import annotations

import pandas as pd

from quant.config import QuantConfig


def apply_filters(factors: pd.DataFrame, config: QuantConfig) -> pd.DataFrame:
    """Attach eligibility flags for factor, volatility, and liquidity constraints.

    Args:
        factors: Factor dataframe containing momentum and risk columns.
        config: Runtime configuration with threshold settings.

    Returns:
        pd.DataFrame: Copy of factors with pass/fail and eligible columns.

    Raises:
        None.
    """
    frame = factors.copy()
    frame["factor_pass"] = frame["momentum_score"].notna()
    frame["volatility_pass"] = frame["volatility_20d"].le(config.volatility_threshold)
    frame["liquidity_pass"] = frame["avg_volume_20d"].ge(config.min_avg_volume)
    frame["eligible"] = frame[["factor_pass", "volatility_pass", "liquidity_pass"]].all(axis=1)
    return frame
