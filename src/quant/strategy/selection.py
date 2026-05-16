"""Weekly position selection based on momentum and filters."""

# File role: derive weekly rebalance dates and choose top-N target positions.

from __future__ import annotations

import numpy as np
import pandas as pd


def weekly_rebalance_dates(dates: pd.Series) -> pd.Series:
    """Compute weekly rebalance dates using Friday-anchored periods.

    Args:
        dates: Series of trading dates.

    Returns:
        pd.Series: Last available trading date for each week.

    Raises:
        None.
    """
    frame = pd.DataFrame({"date": pd.to_datetime(dates).drop_duplicates().sort_values()})
    frame["week"] = frame["date"].dt.to_period("W-FRI")
    return frame.groupby("week", as_index=False)["date"].max()["date"]


def select_weekly_positions(filtered_factors: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """Select top-N eligible symbols per weekly rebalance date.

    Args:
        filtered_factors: Factor dataframe including eligible and momentum_score columns.
        top_n: Maximum number of symbols to select each rebalance date.

    Returns:
        pd.DataFrame: Weekly selected positions with rank and target weights.

    Raises:
        None.
    """
    frame = filtered_factors.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["date", "symbol"]).reset_index(drop=True)

    output_frames: list[pd.DataFrame] = []
    for rebalance_date in weekly_rebalance_dates(frame["date"]):
        snapshot = frame.loc[frame["date"] == rebalance_date].copy()
        snapshot = snapshot.loc[snapshot["eligible"]].dropna(subset=["momentum_score"])
        if snapshot.empty:
            continue

        selected = snapshot.nlargest(top_n, "momentum_score").copy()
        selected["rebalance_date"] = rebalance_date
        selected["rank"] = np.arange(1, len(selected) + 1)
        selected["target_weight"] = 1.0 / len(selected)
        selected["selected_count"] = len(selected)
        output_frames.append(selected)

    if not output_frames:
        return pd.DataFrame(
            columns=[
                "rebalance_date",
                "date",
                "symbol",
                "rank",
                "target_weight",
                "selected_count",
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
        )

    out = pd.concat(output_frames, ignore_index=True)
    return out[
        [
            "rebalance_date",
            "date",
            "symbol",
            "rank",
            "target_weight",
            "selected_count",
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
    ]
