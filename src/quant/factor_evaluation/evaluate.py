"""Factor effectiveness diagnostics for research safety checks."""

# File role: compute factor diagnostics and write evaluation artifacts.

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from quant.config import QuantConfig
from quant.exceptions import DataValidationError
from quant.io_utils import read_parquet_required, write_json, write_parquet
from quant.strategy.selection import weekly_rebalance_dates


def _build_next_week_return_frame(factors: pd.DataFrame, factor_col: str) -> pd.DataFrame:
    """Build a weekly snapshot frame with next-week realized returns.

    Args:
        factors: Factor dataframe containing date, symbol, close, and factor values.
        factor_col: Factor column name to evaluate.

    Returns:
        pd.DataFrame: Weekly rows with next_week_return column.

    Raises:
        DataValidationError: If required columns are missing.
    """
    required = {"date", "symbol", "close", factor_col}
    missing = sorted(required.difference(factors.columns))
    if missing:
        raise DataValidationError(f"Missing columns for factor evaluation: {missing}")

    frame = factors[["date", "symbol", "close", factor_col]].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["symbol", "date"]).reset_index(drop=True)

    rebalance_dates = set(pd.to_datetime(weekly_rebalance_dates(frame["date"])).tolist())
    weekly = frame.loc[frame["date"].isin(rebalance_dates)].copy()
    weekly = weekly.sort_values(["symbol", "date"]).reset_index(drop=True)
    weekly["next_week_return"] = weekly.groupby("symbol")["close"].shift(-1) / weekly["close"] - 1
    return weekly


def _factor_turnover(df: pd.DataFrame, factor_col: str) -> float:
    """Estimate weekly turnover of the top factor bucket.

    Args:
        df: Dataframe with date, symbol, and factor columns.
        factor_col: Factor column name used for ranking.

    Returns:
        float: Mean turnover of top-bucket constituents across weeks.

    Raises:
        None.
    """
    weekly_dates = weekly_rebalance_dates(df["date"])
    prev_top: set[str] | None = None
    turnovers: list[float] = []

    for date in weekly_dates:
        snap = df.loc[df["date"] == date, ["symbol", factor_col]].dropna()
        if snap.empty:
            continue
        cutoff = max(1, int(np.ceil(len(snap) * 0.2)))
        top_symbols = set(snap.nlargest(cutoff, factor_col)["symbol"].astype(str).tolist())

        if prev_top is not None and prev_top:
            overlap = len(prev_top.intersection(top_symbols))
            turnovers.append(1.0 - (overlap / len(prev_top)))

        prev_top = top_symbols

    if not turnovers:
        return float("nan")
    return float(np.mean(turnovers))


def _compute_quantiles(df: pd.DataFrame, factor_col: str) -> pd.DataFrame:
    """Compute per-date forward return averages by factor quantile.

    Args:
        df: Dataframe including date, factor values, and next_week_return.
        factor_col: Factor column to quantile-bin each date.

    Returns:
        pd.DataFrame: Quantile return table with date, quantile, and mean return.

    Raises:
        None.
    """
    out_frames: list[pd.DataFrame] = []

    for date, g in df.groupby("date"):
        sample = g[["date", factor_col, "next_week_return"]].dropna()
        if len(sample) < 5:
            continue

        unique = sample[factor_col].nunique()
        bins = int(min(5, unique))
        if bins < 2:
            continue

        ranked = sample.copy()
        ranked["quantile"] = pd.qcut(
            ranked[factor_col].rank(method="first"),
            q=bins,
            labels=False,
            duplicates="drop",
        )
        grouped = (
            ranked.groupby(["date", "quantile"], as_index=False)["next_week_return"]
            .mean()
            .rename(columns={"next_week_return": "mean_next_return"})
        )
        out_frames.append(grouped)

    if not out_frames:
        return pd.DataFrame(columns=["date", "quantile", "mean_next_return"])

    quantiles = pd.concat(out_frames, ignore_index=True)
    quantiles["quantile"] = quantiles["quantile"].astype(int) + 1
    return quantiles


def evaluate_factor(factors: pd.DataFrame, factor_col: str, min_samples: int) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Evaluate factor quality with coverage and predictive diagnostics.

    Args:
        factors: Factor dataframe containing date, symbol, close, and factor column.
        factor_col: Name of factor column to evaluate.
        min_samples: Minimum non-null sample count required for evaluation.

    Returns:
        tuple[dict, pd.DataFrame, pd.DataFrame]:
            Summary dictionary, per-date IC dataframe, and quantile-return dataframe.

    Raises:
        DataValidationError: If required columns are missing or samples are insufficient.
    """
    frame = _build_next_week_return_frame(factors, factor_col)

    if frame[factor_col].dropna().empty:
        raise DataValidationError(f"{factor_col} is entirely null and cannot be evaluated")

    valid_pairs = frame[[factor_col, "next_week_return"]].dropna()
    if len(valid_pairs) < min_samples:
        raise DataValidationError(
            f"Too few valid samples for {factor_col} evaluation: {len(valid_pairs)} < {min_samples}"
        )

    coverage = frame.groupby("date", as_index=False).agg(
        total_count=("symbol", "count"),
        valid_count=(factor_col, lambda s: int(s.notna().sum())),
    )
    coverage["coverage_pct"] = np.where(
        coverage["total_count"] > 0,
        coverage["valid_count"] / coverage["total_count"],
        np.nan,
    )

    ic_rows: list[dict] = []
    for date, g in frame.groupby("date"):
        sample = g[[factor_col, "next_week_return"]].dropna()
        if len(sample) < 3:
            ic_rows.append({"date": date, "ic": np.nan, "rank_ic": np.nan})
            continue

        if sample[factor_col].std() == 0 or sample["next_week_return"].std() == 0:
            ic_val = np.nan
        else:
            ic_val = sample[factor_col].corr(sample["next_week_return"])

        ranked_factor = sample[factor_col].rank()
        ranked_return = sample["next_week_return"].rank()
        if ranked_factor.std() == 0 or ranked_return.std() == 0:
            rank_ic_val = np.nan
        else:
            rank_ic_val = ranked_factor.corr(ranked_return)
        ic_rows.append({"date": date, "ic": ic_val, "rank_ic": rank_ic_val})

    ic_df = pd.DataFrame(ic_rows)
    ic_df = ic_df.merge(coverage[["date", "valid_count", "coverage_pct"]], on="date", how="left")

    quantiles = _compute_quantiles(frame, factor_col)

    top_bottom = float("nan")
    if not quantiles.empty:
        spread_rows = []
        for date, g in quantiles.groupby("date"):
            low = g.loc[g["quantile"] == g["quantile"].min(), "mean_next_return"]
            high = g.loc[g["quantile"] == g["quantile"].max(), "mean_next_return"]
            if low.empty or high.empty:
                continue
            spread_rows.append(float(high.iloc[0] - low.iloc[0]))
        if spread_rows:
            top_bottom = float(np.mean(spread_rows))

    turnover = _factor_turnover(frame[["date", "symbol", factor_col]], factor_col)

    summary = {
        "factor": factor_col,
        "valid_samples": int(len(valid_pairs)),
        "average_coverage": float(coverage["coverage_pct"].mean()),
        "average_ic": float(ic_df["ic"].mean(skipna=True)),
        "average_rank_ic": float(ic_df["rank_ic"].mean(skipna=True)),
        "top_bottom_spread": top_bottom,
        "factor_turnover": turnover,
        "evaluation_horizon": "next_week_return",
    }
    return summary, ic_df, quantiles


def run(config: QuantConfig, factor_col: str = "momentum_score") -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Run factor evaluation stage and persist diagnostic outputs.

    Args:
        config: Runtime configuration with factor and output paths.
        factor_col: Factor column name to evaluate.

    Returns:
        tuple[dict, pd.DataFrame, pd.DataFrame]:
            Summary dictionary, IC table, and quantile table.

    Raises:
        FileNotFoundError: If factors artifact is missing.
        DataValidationError: If factor data cannot be evaluated safely.
    """
    config.ensure_data_dirs()
    factors = read_parquet_required(config.factors_path)
    summary, ic_df, quantiles = evaluate_factor(
        factors=factors,
        factor_col=factor_col,
        min_samples=config.min_factor_samples,
    )

    write_json(summary, config.factor_eval_dir / f"{factor_col}_summary.json")
    write_parquet(ic_df, config.factor_eval_dir / f"{factor_col}_ic.parquet")
    write_parquet(quantiles, config.factor_eval_dir / f"{factor_col}_quantiles.parquet")
    return summary, ic_df, quantiles
