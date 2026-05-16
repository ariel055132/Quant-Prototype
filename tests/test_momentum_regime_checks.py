"""Validate momentum_regime-focused robustness checks and CSV outputs."""

import pandas as pd

from quant.config import QuantConfig
from quant.experiments.momentum_regime_checks import run_momentum_regime_checks


def test_momentum_regime_checks_write_outputs(tmp_path) -> None:
    """Run momentum_regime checks and verify expected output schemas.

    Args:
        tmp_path: Pytest-provided temporary directory fixture.

    Returns:
        None: Assertion-based test.

    Raises:
        AssertionError: If output files or expected columns are missing.
    """
    config = QuantConfig(
        data_root=tmp_path / "data",
        start_date="2022-01-03",
        end_date="2023-06-30",
        symbols=("2330", "2317", "2454", "2303"),
        min_factor_samples=10,
        top_n=3,
        transaction_cost=0.001,
    )

    output_csv = tmp_path / "momentum_regime_checks_by_seed.csv"
    result = run_momentum_regime_checks(
        base_config=config,
        output_csv=output_csv,
        n_seeds=2,
        top_n_values=(3, 5),
        transaction_cost_values=(0.0, 0.001),
    )

    assert output_csv.exists()
    summary_csv = tmp_path / "momentum_regime_checks_by_seed_summary.csv"
    assert summary_csv.exists()

    loaded = pd.read_csv(output_csv)
    loaded_summary = pd.read_csv(summary_csv)

    assert len(loaded) == 2 * 2 * 2
    assert set(loaded["top_n"].tolist()) == {3, 5}
    assert set(loaded["transaction_cost"].tolist()) == {0.0, 0.001}
    assert loaded.loc[loaded["transaction_cost"] == 0.0, "delta_total_return_vs_cost0"].eq(0.0).all()
    assert loaded["evaluation_horizon"].eq("next_week_return").all()
    assert "total_return_mean" in loaded_summary.columns
    assert "delta_total_return_vs_cost0_mean" in loaded_summary.columns
    assert len(result) == len(loaded)
