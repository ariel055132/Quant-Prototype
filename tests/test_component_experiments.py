"""Validate isolated synthetic-component experiment runner and CSV outputs."""

import pandas as pd

from quant.config import QuantConfig
from quant.experiments.component_test import COMPONENT_NAMES, STRATEGY_MODES, run_component_tests


def test_component_tests_write_summary_csv(tmp_path) -> None:
    """Run isolated component scenarios and verify summary CSV is created.

    Args:
        tmp_path: Pytest-provided temporary directory fixture.

    Returns:
        None: Assertion-based test.

    Raises:
        AssertionError: If CSV output is missing or has incorrect component coverage.
    """
    config = QuantConfig(
        data_root=tmp_path / "data",
        start_date="2022-01-03",
        end_date="2023-06-30",
        symbols=("2330", "2317", "2454", "2303"),
        min_factor_samples=10,
        top_n=2,
    )

    output_csv = tmp_path / "component_test_summary.csv"
    result = run_component_tests(config, output_csv=output_csv, n_seeds=2)

    assert output_csv.exists()
    by_seed_csv = tmp_path / "component_test_summary_by_seed.csv"
    assert by_seed_csv.exists()

    loaded = pd.read_csv(output_csv)
    loaded_by_seed = pd.read_csv(by_seed_csv)

    assert len(loaded) == len(COMPONENT_NAMES) * len(STRATEGY_MODES)
    assert len(loaded_by_seed) == len(COMPONENT_NAMES) * len(STRATEGY_MODES) * 2
    assert set(loaded["component"].tolist()) == set(COMPONENT_NAMES)
    assert set(loaded["strategy_mode"].tolist()) == set(STRATEGY_MODES)
    assert loaded.loc[loaded["strategy_mode"] == "momentum_top_n_filtered", "is_benchmark"].eq(False).all()
    assert loaded.loc[loaded["strategy_mode"] != "momentum_top_n_filtered", "is_benchmark"].eq(True).all()
    assert "total_return_mean" in loaded.columns
    assert "total_return_std" in loaded.columns
    assert "delta_sharpe_vs_momentum_mean" in loaded.columns
    assert "seed_runs" in loaded.columns
    assert loaded["seed_runs"].eq(2).all()
    assert set(result["component"].tolist()) == set(COMPONENT_NAMES)
