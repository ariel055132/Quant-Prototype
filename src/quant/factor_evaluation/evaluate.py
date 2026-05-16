"""Factor effectiveness diagnostics for research safety checks."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from quant.config import QuantConfig
from quant.exceptions import DataValidationError
from quant.io_utils import read_parquet_required, write_json, write_parquet


def _weekly_rebalance_dates(dates: pd.Series) -> pd.Series:
    frame = pd.DataFrame({"date": pd.to_datetime(dates).drop_duplicates().sort_values()})
    frame["week"] = frame["date"].dt.to_period("W-FRI")
    return frame.groupby("week", as_index=False)["date"].max()["date"]


def _factor_turnover(df: pd.DataFrame, factor_col: str) -> float:
    weekly_dates = _weekly_rebalance_dates(df["date"])
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
    out_frames: list[pd.DataFrame] = []

    for date, g in df.groupby("date"):
        sample = g[["date", factor_col, "next_return_5d"]].dropna()
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
            ranked.groupby(["date", "quantile"], as_index=False)["next_return_5d"]
            .mean()
            .rename(columns={"next_return_5d": "mean_next_return"})
        )
        out_frames.append(grouped)

    if not out_frames:
        return pd.DataFrame(columns=["date", "quantile", "mean_next_return"])

    quantiles = pd.concat(out_frames, ignore_index=True)
    quantiles["quantile"] = quantiles["quantile"].astype(int) + 1
    return quantiles


def evaluate_factor(factors: pd.DataFrame, factor_col: str, min_samples: int) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Evaluate a factor with coverage, IC, rank-IC, spread, and turnover diagnostics."""
    required = {"date", "symbol", "close", factor_col}
    missing = sorted(required.difference(factors.columns))
    if missing:
        raise DataValidationError(f"Missing columns for factor evaluation: {missing}")

    frame = factors[["date", "symbol", "close", factor_col]].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["symbol", "date"]).reset_index(drop=True)
    frame["next_return_5d"] = frame.groupby("symbol")["close"].shift(-5) / frame["close"] - 1

    if frame[factor_col].dropna().empty:
        raise DataValidationError(f"{factor_col} is entirely null and cannot be evaluated")

    valid_pairs = frame[[factor_col, "next_return_5d"]].dropna()
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
        sample = g[[factor_col, "next_return_5d"]].dropna()
        if len(sample) < 3:
            ic_rows.append({"date": date, "ic": np.nan, "rank_ic": np.nan})
            continue

        ic_val = sample[factor_col].corr(sample["next_return_5d"])
        rank_ic_val = sample[factor_col].rank().corr(sample["next_return_5d"].rank())
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
    }
    return summary, ic_df, quantiles


def run(config: QuantConfig, factor_col: str = "momentum_score") -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Execute factor evaluation stage and write diagnostics artifacts."""
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
