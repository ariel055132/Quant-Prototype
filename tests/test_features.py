"""Verify factor calculations remain grouped by symbol without leakage."""

import numpy as np
import pandas as pd

from quant.features.build import build_factors


def test_factor_calculation_grouped_by_symbol() -> None:
    """Verify rolling factor logic is isolated within each symbol group.

    Args:
        None.

    Returns:
        None: Assertion-based test.

    Raises:
        AssertionError: If factor calculations leak across symbols.
    """
    dates = pd.bdate_range("2024-01-01", periods=40)

    a = pd.DataFrame(
        {
            "date": dates,
            "symbol": "A",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1_000_000,
        }
    )
    b = pd.DataFrame(
        {
            "date": dates,
            "symbol": "B",
            "open": np.linspace(50, 80, len(dates)),
            "high": np.linspace(51, 81, len(dates)),
            "low": np.linspace(49, 79, len(dates)),
            "close": np.linspace(50, 80, len(dates)),
            "volume": 1_500_000,
        }
    )

    out = build_factors(pd.concat([a, b], ignore_index=True))

    a_returns = out.loc[out["symbol"] == "A", "return_20d"]
    assert a_returns.iloc[:20].isna().all()
    assert a_returns.iloc[20:].fillna(0.0).eq(0.0).all()
