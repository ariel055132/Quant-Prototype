"""Preprocess and validate raw OHLCV data."""

# File role: enforce OHLCV data contracts and write cleaned prices.

from __future__ import annotations

import pandas as pd

from quant.config import QuantConfig
from quant.exceptions import DataValidationError, EmptyDatasetError
from quant.io_utils import read_parquet_required, write_parquet

REQUIRED_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "volume"]
PRICE_COLUMNS = ["open", "high", "low", "close"]


def _validate_columns(df: pd.DataFrame) -> None:
    """Validate presence of required price columns.

    Args:
        df: Input dataframe expected to contain OHLCV columns.

    Returns:
        None: Validation only.

    Raises:
        DataValidationError: If one or more required columns are missing.
    """
    missing = sorted(set(REQUIRED_COLUMNS).difference(df.columns))
    if missing:
        raise DataValidationError(f"Missing required columns: {missing}")


def _parse_and_validate_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert date column to datetime and reject invalid date values.

    Args:
        df: Input dataframe containing a date column.

    Returns:
        pd.DataFrame: Copy of input with parsed datetime date column.

    Raises:
        DataValidationError: If any date value cannot be parsed.
    """
    parsed = pd.to_datetime(df["date"], errors="coerce")
    if parsed.isna().any():
        raise DataValidationError("Invalid dates detected in date column")
    df = df.copy()
    df["date"] = parsed
    return df


def _validate_ohlcv(df: pd.DataFrame) -> None:
    """Validate OHLC and volume constraints.

    Args:
        df: Dataframe with OHLCV columns.

    Returns:
        None: Validation only.

    Raises:
        DataValidationError: If price positivity, high/low, or volume rules fail.
    """
    if (df[PRICE_COLUMNS] <= 0).any().any():
        raise DataValidationError("OHLC prices must be positive")

    if (df["high"] < df["low"]).any():
        raise DataValidationError("Detected rows where high < low")

    if (df["volume"] < 0).any():
        raise DataValidationError("Volume must be non-negative")


def process_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and validate raw OHLCV rows.

    Args:
        df: Raw prices dataframe.

    Returns:
        pd.DataFrame: Deduplicated and validated prices sorted by symbol/date.

    Raises:
        DataValidationError: If column, date, or OHLCV constraints fail.
        EmptyDatasetError: If all rows are removed by preprocessing.
    """
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
    """Run preprocessing stage and write cleaned prices parquet.

    Args:
        config: Runtime configuration with input/output paths.

    Returns:
        pd.DataFrame: Processed prices dataframe.

    Raises:
        FileNotFoundError: If raw prices artifact is missing.
        EmptyDatasetError: If input or processed datasets are empty.
        DataValidationError: If preprocessing validation fails.
    """
    config.ensure_data_dirs()
    raw_df = read_parquet_required(config.raw_prices_path)
    processed_df = process_prices(raw_df)
    write_parquet(processed_df, config.processed_prices_path)
    return processed_df
