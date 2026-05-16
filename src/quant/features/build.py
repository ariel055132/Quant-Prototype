"""Build price-based factors from processed OHLCV data."""

from __future__ import annotations

import numpy as np
import pandas as pd

from quant.config import QuantConfig
from quant.exceptions import EmptyDatasetError
from quant.io_utils import read_parquet_required, write_parquet


def build_factors(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute grouped rolling factors without look-ahead."""
    ordered = prices.sort_values(["symbol", "date"]).reset_index(drop=True).copy()
    grouped = ordered.groupby("symbol", group_keys=False)

    ordered["return_20d"] = grouped["close"].pct_change(periods=20)
    ordered["return_60d"] = grouped["close"].pct_change(periods=60)
    ordered["ma_20"] = grouped["close"].transform(lambda s: s.rolling(window=20, min_periods=20).mean())

    daily_returns = grouped["close"].pct_change(periods=1)
    ordered["volatility_20d"] = daily_returns.groupby(ordered["symbol"]).transform(
        lambda s: s.rolling(window=20, min_periods=20).std()
    )
    ordered["avg_volume_20d"] = grouped["volume"].transform(
        lambda s: s.rolling(window=20, min_periods=20).mean()
    )

    # A simple first-pass score: favor medium-term return and penalize volatility.
    ordered["momentum_score"] = (
        0.6 * ordered["return_20d"]
        + 0.4 * ordered["return_60d"]
        - 0.2 * ordered["volatility_20d"]
    )

    if ordered.empty:
        raise EmptyDatasetError("Factor dataset is empty")

    return ordered


def run(config: QuantConfig) -> pd.DataFrame:
    """Execute factor build stage and write factors parquet."""
    config.ensure_data_dirs()
    processed = read_parquet_required(config.processed_prices_path)
    factors = build_factors(processed)
    write_parquet(factors, config.factors_path)
    return factors
