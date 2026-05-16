"""Synthetic Taiwan-equity-style OHLCV data generation."""

# File role: generate reproducible synthetic market data and persist raw prices.

from __future__ import annotations

import numpy as np
import pandas as pd

from quant.config import QuantConfig
from quant.io_utils import write_parquet

REQUIRED_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "volume"]
SYNTHETIC_PROPERTY_COLUMNS = [
    "random_walk_no_drift",
    "market_drift",
    "momentum_regime",
    "mean_reversion_regime",
]


def _generate_regime_sequence(rng: np.random.Generator, length: int) -> list[str]:
    """Generate persistent per-symbol regimes for synthetic return dynamics.

    Args:
        rng: Random number generator.
        length: Number of dates to generate.

    Returns:
        list[str]: Regime labels for each date.

    Raises:
        None.
    """
    regimes = ["momentum", "mean_reversion", "neutral"]
    transition = {
        "momentum": [0.75, 0.05, 0.20],
        "mean_reversion": [0.10, 0.70, 0.20],
        "neutral": [0.50, 0.15, 0.35],
    }

    current = str(rng.choice(regimes, p=[0.55, 0.20, 0.25]))
    out: list[str] = []
    for _ in range(length):
        out.append(current)
        current = str(rng.choice(regimes, p=transition[current]))
    return out


def generate_synthetic_prices(config: QuantConfig) -> pd.DataFrame:
    """Generate reproducible synthetic daily OHLCV data.

    Args:
        config: Runtime configuration containing seed, date range, and symbols.

    Returns:
        pd.DataFrame: Synthetic OHLCV rows sorted by symbol and date.

    Raises:
        None.
    """
    rng = np.random.default_rng(config.seed)
    dates = pd.bdate_range(start=config.start_date, end=config.end_date)
    market_shocks = rng.normal(loc=0.0, scale=0.006, size=len(dates))

    records: list[dict] = []
    for symbol in config.symbols:
        base_price = rng.uniform(30.0, 900.0)
        market_beta = rng.uniform(0.7, 1.3)
        idio_scale = rng.uniform(0.85, 1.15)
        regimes = _generate_regime_sequence(rng, len(dates))
        volume_base = rng.integers(700_000, 6_000_000)

        prev_close = float(base_price)
        recent_returns: list[float] = []

        for idx, date in enumerate(dates):
            trailing_5d_signal = float(np.sum(recent_returns[-5:])) if recent_returns else 0.0

            random_walk_no_drift = float(
                rng.normal(loc=0.0, scale=config.random_walk_no_drift * idio_scale)
            )
            market_drift = (
                float(config.market_drift + market_beta * market_shocks[idx])
                if config.market_drift != 0.0
                else 0.0
            )

            regime = regimes[idx]
            if regime == "momentum":
                momentum_innovation = (
                    float(rng.normal(loc=0.0, scale=abs(config.momentum_regime) * 0.002))
                    if config.momentum_regime != 0.0
                    else 0.0
                )
                momentum_regime = float(
                    config.momentum_regime * (trailing_5d_signal / 5.0) + momentum_innovation
                )
                mean_reversion_regime = 0.0
            elif regime == "mean_reversion":
                momentum_regime = 0.0
                mean_reversion_innovation = (
                    float(rng.normal(loc=0.0, scale=abs(config.mean_reversion_regime) * 0.002))
                    if config.mean_reversion_regime != 0.0
                    else 0.0
                )
                mean_reversion_regime = float(
                    -config.mean_reversion_regime * (trailing_5d_signal / 5.0)
                    + mean_reversion_innovation
                )
            else:
                momentum_regime = 0.0
                mean_reversion_regime = 0.0

            total_return = float(
                np.clip(
                    random_walk_no_drift + market_drift + momentum_regime + mean_reversion_regime,
                    -0.12,
                    0.12,
                )
            )

            open_price = float(max(prev_close * np.exp(rng.normal(0.0, 0.004)), 0.5))
            close_price = float(max(prev_close * np.exp(total_return), 0.5))

            high_anchor = max(open_price, close_price)
            low_anchor = min(open_price, close_price)
            high_price = float(high_anchor * (1 + abs(rng.normal(0.0025, 0.004))))
            low_price = float(max(low_anchor * (1 - abs(rng.normal(0.0025, 0.004))), 0.3))

            volume_regime_boost = 0.20 if regime == "momentum" else 0.10 if regime == "mean_reversion" else 0.0
            volume_scale = 1 + min(abs(total_return) * 12, 2.0) + volume_regime_boost
            volume = int(max(volume_base * volume_scale * (1 + rng.normal(0.0, 0.25)), 0))

            records.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                    "random_walk_no_drift": random_walk_no_drift,
                    "market_drift": market_drift,
                    "momentum_regime": momentum_regime,
                    "mean_reversion_regime": mean_reversion_regime,
                }
            )

            recent_returns.append(total_return)
            prev_close = close_price

    df = pd.DataFrame.from_records(records, columns=REQUIRED_COLUMNS + SYNTHETIC_PROPERTY_COLUMNS)
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def run(config: QuantConfig) -> pd.DataFrame:
    """Run data generation and persist raw prices.

    Args:
        config: Runtime configuration with output directory settings.

    Returns:
        pd.DataFrame: Generated raw prices dataframe.

    Raises:
        None.
    """
    config.ensure_data_dirs()
    df = generate_synthetic_prices(config)
    write_parquet(df, config.raw_prices_path)
    return df
