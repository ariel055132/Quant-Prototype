"""Weekly candidate export for manual review."""

from __future__ import annotations

import pandas as pd

from quant.config import QuantConfig
from quant.exceptions import DataValidationError
from quant.filters.risk import apply_filters
from quant.io_utils import read_parquet_required, write_parquet
from quant.strategy.selection import select_weekly_positions


def export_candidates(config: QuantConfig, rebalance_date: str | None = None) -> pd.DataFrame:
    """Export latest or specific rebalance-date candidates."""
    factors = read_parquet_required(config.factors_path)
    filtered = apply_filters(factors, config)
    positions = select_weekly_positions(filtered, config.top_n)
    if positions.empty:
        raise DataValidationError("No candidates available after applying filters")

    positions["rebalance_date"] = pd.to_datetime(positions["rebalance_date"])

    if rebalance_date is None:
        target_date = positions["rebalance_date"].max()
    else:
        target_date = pd.to_datetime(rebalance_date, errors="coerce")
        if pd.isna(target_date):
            raise DataValidationError(f"Invalid rebalance date: {rebalance_date}")

    candidates = positions.loc[positions["rebalance_date"] == target_date].copy()
    if candidates.empty:
        raise DataValidationError(f"No candidates found for rebalance_date={target_date.date()}")

    out = candidates[
        [
            "rebalance_date",
            "symbol",
            "rank",
            "momentum_score",
            "return_20d",
            "return_60d",
            "volatility_20d",
            "avg_volume_20d",
            "factor_pass",
            "volatility_pass",
            "liquidity_pass",
            "eligible",
        ]
    ].sort_values("rank")

    write_parquet(out, config.signals_dir / "weekly_candidates.parquet")
    return out


def run(config: QuantConfig, rebalance_date: str | None = None) -> pd.DataFrame:
    """Execute candidate export stage."""
    config.ensure_data_dirs()
    return export_candidates(config, rebalance_date=rebalance_date)
