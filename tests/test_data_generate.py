"""Validate synthetic data generation contracts and reproducibility."""

import pandas as pd

from quant.config import QuantConfig
from quant.data.generate import REQUIRED_COLUMNS, SYNTHETIC_PROPERTY_COLUMNS, generate_synthetic_prices


def test_synthetic_data_is_reproducible() -> None:
    """Ensure same seed and config generate identical synthetic data.

    Args:
        None.

    Returns:
        None: Assertion-based test.

    Raises:
        AssertionError: If generated dataframes differ.
    """
    config = QuantConfig(
        seed=7,
        start_date="2022-01-03",
        end_date="2022-04-29",
        symbols=("2330", "2317", "2454"),
    )

    first = generate_synthetic_prices(config)
    second = generate_synthetic_prices(config)

    pd.testing.assert_frame_equal(first, second)


def test_synthetic_data_has_required_shape() -> None:
    """Check generated data meets required columns and basic constraints.

    Args:
        None.

    Returns:
        None: Assertion-based test.

    Raises:
        AssertionError: If generated data violates expected constraints.
    """
    config = QuantConfig(
        start_date="2022-01-03",
        end_date="2022-06-30",
        symbols=("2330", "2317", "2454"),
    )
    df = generate_synthetic_prices(config)

    for col in REQUIRED_COLUMNS + SYNTHETIC_PROPERTY_COLUMNS:
        assert col in df.columns
    assert df["symbol"].nunique() >= 3
    assert df["date"].nunique() >= 100
    assert (df[["open", "high", "low", "close"]] > 0).all().all()
    assert (df["volume"] >= 0).all()
    assert not df.duplicated(subset=["date", "symbol"]).any()
    assert df[SYNTHETIC_PROPERTY_COLUMNS].notna().all().all()
