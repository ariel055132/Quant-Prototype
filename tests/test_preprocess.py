"""Check preprocessing rules for deduplication and OHLCV validation errors."""

import pandas as pd
import pytest

from quant.exceptions import DataValidationError
from quant.preprocess.process import process_prices


def test_preprocess_removes_duplicate_symbol_date() -> None:
    """Ensure duplicate date+symbol rows are removed during preprocessing.

    Args:
        None.

    Returns:
        None: Assertion-based test.

    Raises:
        AssertionError: If duplicates remain after preprocessing.
    """
    df = pd.DataFrame(
        [
            {"date": "2024-01-02", "symbol": "2330", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
            {"date": "2024-01-02", "symbol": "2330", "open": 100, "high": 103, "low": 99, "close": 102, "volume": 2000},
            {"date": "2024-01-03", "symbol": "2330", "open": 102, "high": 104, "low": 101, "close": 103, "volume": 1500},
        ]
    )

    out = process_prices(df)
    assert len(out) == 2
    assert not out.duplicated(subset=["date", "symbol"]).any()


def test_preprocess_rejects_invalid_ohlcv() -> None:
    """Ensure invalid OHLC relationships raise a validation error.

    Args:
        None.

    Returns:
        None: Assertion-based test.

    Raises:
        AssertionError: If invalid OHLC rows are not rejected.
    """
    df = pd.DataFrame(
        [
            {"date": "2024-01-02", "symbol": "2330", "open": 100, "high": 98, "low": 99, "close": 101, "volume": 1000},
        ]
    )

    with pytest.raises(DataValidationError, match="high < low"):
        process_prices(df)
