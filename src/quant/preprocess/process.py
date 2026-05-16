"""Preprocess and validate raw OHLCV data."""

from __future__ import annotations

import pandas as pd

from quant.config import QuantConfig
from quant.exceptions import DataValidationError, EmptyDatasetError
from quant.io_utils import read_parquet_required, write_parquet

REQUIRED_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "volume"]
PRICE_COLUMNS = ["open", "high", "low", "close"]


def _validate_columns(df: pd.DataFrame) -> None:
    missing = sorted(set(REQUIRED_COLUMNS).difference(df.columns))
    if missing:
        raise DataValidationError(f"Missing required columns: {missing}")


def _parse_and_validate_dates(df: pd.DataFrame) -> pd.DataFrame:
    parsed = pd.to_datetime(df["date"], errors="coerce")
    if parsed.isna().any():
        raise DataValidationError("Invalid dates detected in date column")
    df = df.copy()
    df["date"] = parsed
    return df


def _validate_ohlcv(df: pd.DataFrame) -> None:
    if (df[PRICE_COLUMNS] <= 0).any().any():
        raise DataValidationError("OHLC prices must be positive")

    if (df["high"] < df["low"]).any():
        raise DataValidationError("Detected rows where high < low")

    if (df["volume"] < 0).any():
        raise DataValidationError("Volume must be non-negative")


def process_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Apply required cleaning and validation rules to raw prices."""
    _validate_columns(df)
    df = _parse_and_validate_dates(df)

    deduped = (
        df.sort_values(["symbol", "date"])  # Stable ordering for deterministic drops.
        .drop_duplicates(subset=["date", "symbol"], keep="last")
        .reset_index(drop=True)
    )

    if deduped.empty:
        raise EmptyDatasetError("Processed dataset is empty after deduplication")

    _validate_ohlcv(deduped)
    return deduped


def run(config: QuantConfig) -> pd.DataFrame:
    """Execute preprocessing stage and write cleaned prices."""
    config.ensure_data_dirs()
    raw_df = read_parquet_required(config.raw_prices_path)
    processed_df = process_prices(raw_df)
    write_parquet(processed_df, config.processed_prices_path)
    return processed_df
