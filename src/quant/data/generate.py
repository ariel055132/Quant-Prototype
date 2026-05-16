"""Synthetic Taiwan-equity-style OHLCV data generation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from quant.config import QuantConfig
from quant.io_utils import write_parquet

REQUIRED_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "volume"]


def generate_synthetic_prices(config: QuantConfig) -> pd.DataFrame:
    """Generate reproducible synthetic daily OHLCV data."""
    rng = np.random.default_rng(config.seed)
    dates = pd.bdate_range(start=config.start_date, end=config.end_date)

    records: list[dict] = []
    for symbol in config.symbols:
        base_price = rng.uniform(30.0, 900.0)
        daily_shocks = rng.normal(loc=0.0004, scale=0.02, size=len(dates))
        close_series = base_price * np.exp(np.cumsum(daily_shocks))

        # Use previous close as open anchor and keep OHLC consistency.
        prev_close = np.roll(close_series, 1)
        prev_close[0] = base_price
        open_series = np.maximum(prev_close * (1 + rng.normal(0.0, 0.005, len(dates))), 0.5)

        high_anchor = np.maximum(open_series, close_series)
        low_anchor = np.minimum(open_series, close_series)
        high_series = high_anchor * (1 + np.abs(rng.normal(0.002, 0.004, len(dates))))
        low_series = np.maximum(low_anchor * (1 - np.abs(rng.normal(0.002, 0.004, len(dates)))), 0.3)

        volume_base = rng.integers(700_000, 6_000_000)
        volume_series = np.maximum(
            (volume_base * (1 + rng.normal(0.0, 0.35, len(dates)))).astype(int),
            0,
        )

        for idx, date in enumerate(dates):
            records.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "open": float(open_series[idx]),
                    "high": float(high_series[idx]),
                    "low": float(low_series[idx]),
                    "close": float(close_series[idx]),
                    "volume": int(volume_series[idx]),
                }
            )

    df = pd.DataFrame.from_records(records, columns=REQUIRED_COLUMNS)
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def run(config: QuantConfig) -> pd.DataFrame:
    """Execute data generation stage and write the raw parquet artifact."""
    config.ensure_data_dirs()
    df = generate_synthetic_prices(config)
    write_parquet(df, config.raw_prices_path)
    return df
