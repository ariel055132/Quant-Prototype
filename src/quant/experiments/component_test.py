"""Run single-component synthetic property experiments and export CSV summaries."""

# File role: execute one-property-at-a-time experiments for synthetic return components.

from __future__ import annotations

import zlib
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from quant.backtest.run import _max_drawdown
from quant.config import QuantConfig
from quant.data.generate import run as run_generate
from quant.factor_evaluation.evaluate import run as run_factor_evaluate
from quant.features.build import run as run_features
from quant.filters.risk import apply_filters
from quant.preprocess.process import run as run_preprocess
from quant.strategy.selection import select_weekly_positions
from quant.strategy.selection import weekly_rebalance_dates

COMPONENT_NAMES = [
    "random_walk_no_drift",
    "market_drift",
    "momentum_regime",
    "mean_reversion_regime",
]

STRATEGY_MODES = [
    "momentum_top_n_filtered",
    "equal_weight_all",
    "random_top_n_all",
    "random_top_n_filtered",
]


def _config_for_component(
    base_config: QuantConfig,
    component: str,
    component_root: Path,
    seed: int,
) -> QuantConfig:
    """Build a config where one synthetic component is active and others are disabled.

    Args:
        base_config: Base runtime configuration.
        component: Component name to keep active.
        component_root: Data root path for this component run.
        seed: Seed used for this scenario run.

    Returns:
        QuantConfig: Scenario config for isolated component testing.

    Raises:
        ValueError: If component is not a supported property name.
    """
    if component not in COMPONENT_NAMES:
        raise ValueError(f"Unsupported component: {component}")

    return replace(
        base_config,
        data_root=component_root,
        seed=seed,
        random_walk_no_drift=base_config.random_walk_no_drift if component == "random_walk_no_drift" else 0.0,
        market_drift=base_config.market_drift if component == "market_drift" else 0.0,
        momentum_regime=base_config.momentum_regime if component == "momentum_regime" else 0.0,
        mean_reversion_regime=base_config.mean_reversion_regime if component == "mean_reversion_regime" else 0.0,
    )


def _seed_for_mode(base_seed: int, component: str, mode: str) -> int:
    """Build a deterministic RNG seed for a component/mode pair.

    Args:
        base_seed: Base experiment seed.
        component: Component name.
        mode: Strategy mode name.

    Returns:
        int: Stable 32-bit seed.

    Raises:
        None.
    """
    key = f"{base_seed}:{component}:{mode}".encode("utf-8")
    return int(zlib.crc32(key) & 0xFFFFFFFF)


def _positions_equal_weight_all(prices: pd.DataFrame) -> pd.DataFrame:
    """Create weekly equal-weight positions across all available symbols.

    Args:
        prices: Processed price dataframe with date and symbol columns.

    Returns:
        pd.DataFrame: Position table with rebalance date, symbol, and target weight.

    Raises:
        None.
    """
    frame = prices[["date", "symbol"]].copy()
    frame["date"] = pd.to_datetime(frame["date"])

    rows: list[dict] = []
    for rebalance_date in weekly_rebalance_dates(frame["date"]):
        snapshot = frame.loc[frame["date"] == rebalance_date, ["symbol"]].drop_duplicates()
        count = len(snapshot)
        if count == 0:
            continue

        snapshot = snapshot.sort_values("symbol").reset_index(drop=True)
        weight = 1.0 / count
        for rank, symbol in enumerate(snapshot["symbol"].tolist(), start=1):
            rows.append(
                {
                    "rebalance_date": rebalance_date,
                    "symbol": symbol,
                    "target_weight": weight,
                    "rank": rank,
                    "selected_count": count,
                }
            )

    return pd.DataFrame(rows)


def _positions_momentum_filtered(factors: pd.DataFrame, config: QuantConfig) -> pd.DataFrame:
    """Create weekly momentum top-N positions after risk/liquidity filters.

    Args:
        factors: Factor dataframe with momentum_score and filter-required columns.
        config: Runtime configuration containing top_n and filter thresholds.

    Returns:
        pd.DataFrame: Position table with rebalance_date, symbol, and target_weight.

    Raises:
        None.
    """
    filtered = apply_filters(factors, config)
    positions = select_weekly_positions(filtered, config.top_n)
    if positions.empty:
        return pd.DataFrame(columns=["rebalance_date", "symbol", "target_weight", "rank", "selected_count"])

    return positions[["rebalance_date", "symbol", "target_weight", "rank", "selected_count"]].copy()


def _positions_random_top_n(universe: pd.DataFrame, top_n: int, seed: int) -> pd.DataFrame:
    """Create weekly random top-N positions from a date-symbol universe.

    Args:
        universe: Dataframe with date and symbol columns defining candidate stocks.
        top_n: Maximum number of symbols to select each rebalance date.
        seed: RNG seed for deterministic sampling.

    Returns:
        pd.DataFrame: Position table with rebalance date, symbol, and target weight.

    Raises:
        None.
    """
    frame = universe[["date", "symbol"]].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    rng = np.random.default_rng(seed)

    rows: list[dict] = []
    for rebalance_date in weekly_rebalance_dates(frame["date"]):
        snapshot = frame.loc[frame["date"] == rebalance_date, ["symbol"]].drop_duplicates()
        symbols = snapshot["symbol"].astype(str).tolist()
        if not symbols:
            continue

        take_n = min(top_n, len(symbols))
        selected = rng.choice(np.array(symbols, dtype=object), size=take_n, replace=False).tolist()
        selected = sorted(selected)
        weight = 1.0 / take_n
        for rank, symbol in enumerate(selected, start=1):
            rows.append(
                {
                    "rebalance_date": rebalance_date,
                    "symbol": symbol,
                    "target_weight": weight,
                    "rank": rank,
                    "selected_count": take_n,
                }
            )

    return pd.DataFrame(rows)


def _align_positions_for_comparison(
    mode_positions: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[pd.Timestamp]]:
    """Align all strategy modes to a shared rebalance calendar for fair comparison.

    Args:
        mode_positions: Mapping of strategy mode to weekly positions dataframe.

    Returns:
        tuple[dict[str, pd.DataFrame], list[pd.Timestamp]]:
            Aligned position map and sorted shared rebalance dates.

    Raises:
        ValueError: If modes cannot share at least two rebalance dates.
    """
    normalized: dict[str, pd.DataFrame] = {}
    date_sets: list[set[pd.Timestamp]] = []

    for mode, positions in mode_positions.items():
        frame = positions.copy()
        if frame.empty:
            raise ValueError(f"No positions generated for mode={mode}")

        frame["rebalance_date"] = pd.to_datetime(frame["rebalance_date"])
        unique_dates = set(pd.to_datetime(frame["rebalance_date"].dropna().unique()).tolist())
        if len(unique_dates) < 2:
            raise ValueError(f"Insufficient rebalance dates for mode={mode}")

        normalized[mode] = frame
        date_sets.append(unique_dates)

    shared_dates = sorted(set.intersection(*date_sets))
    if len(shared_dates) < 2:
        raise ValueError("No shared rebalance window across strategy modes")

    aligned: dict[str, pd.DataFrame] = {}
    for mode, frame in normalized.items():
        aligned_frame = frame.loc[frame["rebalance_date"].isin(shared_dates)].copy()
        if aligned_frame["rebalance_date"].nunique() < 2:
            raise ValueError(f"Aligned window too short for mode={mode}")
        aligned[mode] = aligned_frame

    return aligned, [pd.Timestamp(d) for d in shared_dates]


def _run_backtest_from_positions(
    prices: pd.DataFrame,
    positions: pd.DataFrame,
    config: QuantConfig,
) -> dict:
    """Simulate backtest metrics from externally supplied weekly positions.

    Args:
        prices: Processed OHLCV dataframe.
        positions: Weekly position table with rebalance_date, symbol, and target_weight.
        config: Runtime configuration containing cash and cost settings.

    Returns:
        dict: Backtest summary metrics aligned with standard summary schema.

    Raises:
        ValueError: If positions are empty or cannot form a valid equity curve.
    """
    if positions.empty:
        raise ValueError("No positions available for benchmark simulation")

    prices_frame = prices.copy()
    prices_frame["date"] = pd.to_datetime(prices_frame["date"])

    positions_frame = positions.copy()
    positions_frame["rebalance_date"] = pd.to_datetime(positions_frame["rebalance_date"])

    close_lookup = prices_frame.pivot(index="date", columns="symbol", values="close").sort_index()
    rebalance_dates = sorted(positions_frame["rebalance_date"].dropna().unique().tolist())
    if len(rebalance_dates) < 2:
        raise ValueError("Need at least two rebalance dates for benchmark simulation")

    equity = float(config.initial_cash)
    prev_weights: dict[str, float] = {}
    equity_rows: list[dict] = []

    for idx in range(len(rebalance_dates) - 1):
        rebalance_date = pd.to_datetime(rebalance_dates[idx])
        next_date = pd.to_datetime(rebalance_dates[idx + 1])

        basket = positions_frame.loc[
            positions_frame["rebalance_date"] == rebalance_date,
            ["symbol", "target_weight"],
        ].copy()
        if basket.empty:
            continue

        valid_returns: list[float] = []
        current_weights: dict[str, float] = {}

        for row in basket.itertuples(index=False):
            symbol = str(row.symbol)
            if symbol not in close_lookup.columns:
                continue

            start_px = close_lookup.at[rebalance_date, symbol] if rebalance_date in close_lookup.index else np.nan
            end_px = close_lookup.at[next_date, symbol] if next_date in close_lookup.index else np.nan
            if pd.isna(start_px) or pd.isna(end_px) or start_px <= 0:
                continue

            current_weights[symbol] = float(row.target_weight)
            valid_returns.append(float(end_px / start_px - 1.0))

        if not valid_returns:
            continue

        gross_return = float(np.mean(valid_returns))
        all_symbols = set(prev_weights).union(current_weights)
        turnover = 0.5 * sum(abs(current_weights.get(s, 0.0) - prev_weights.get(s, 0.0)) for s in all_symbols)
        cost = turnover * config.transaction_cost
        net_return = gross_return - cost

        equity *= 1.0 + net_return
        equity_rows.append(
            {
                "date": next_date,
                "net_return": net_return,
                "equity": equity,
            }
        )
        prev_weights = current_weights

    equity_curve = pd.DataFrame(equity_rows)
    if equity_curve.empty:
        raise ValueError("Benchmark equity curve is empty")

    weekly_returns = equity_curve["net_return"]
    days = (pd.to_datetime(equity_curve["date"].iloc[-1]) - pd.to_datetime(rebalance_dates[0])).days
    years = max(days / 365.25, 1 / 52)
    total_return = float(equity_curve["equity"].iloc[-1] / config.initial_cash - 1.0)
    cagr = float((equity_curve["equity"].iloc[-1] / config.initial_cash) ** (1 / years) - 1.0)
    sharpe = float(np.sqrt(52) * weekly_returns.mean() / weekly_returns.std()) if weekly_returns.std() > 0 else 0.0

    return {
        "start_date": str(pd.to_datetime(rebalance_dates[0]).date()),
        "end_date": str(pd.to_datetime(equity_curve["date"].iloc[-1]).date()),
        "initial_cash": float(config.initial_cash),
        "final_equity": float(equity_curve["equity"].iloc[-1]),
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": float(_max_drawdown(equity_curve["equity"])),
        "number_of_trading_days": int(prices_frame["date"].nunique()),
        "rebalance_frequency": config.rebalance_frequency,
        "selected_count_average": float(positions_frame.groupby("rebalance_date")["symbol"].count().mean()),
        "transaction_cost": float(config.transaction_cost),
    }


def run_component_tests(
    base_config: QuantConfig,
    output_csv: Path | None = None,
    n_seeds: int = 3,
) -> pd.DataFrame:
    """Run isolated component scenarios with benchmarks and write CSV summaries.

    Args:
        base_config: Base runtime configuration used as the experiment template.
        output_csv: Optional custom destination for aggregated CSV output.
        n_seeds: Number of seeds to run for each component scenario.

    Returns:
        pd.DataFrame: Aggregated summary with mean/std metrics by component and mode.

    Raises:
        ValueError: If any component/mode cannot generate a shared rebalance window.
    """
    if n_seeds < 1:
        raise ValueError("n_seeds must be at least 1")

    experiments_root = base_config.data_root / "experiments" / "component_tests"
    seed_rows: list[dict] = []

    for component in COMPONENT_NAMES:
        for seed_idx in range(n_seeds):
            scenario_seed = base_config.seed + seed_idx
            component_root = experiments_root / component / f"seed_{scenario_seed}"
            scenario_config = _config_for_component(
                base_config=base_config,
                component=component,
                component_root=component_root,
                seed=scenario_seed,
            )

            run_generate(scenario_config)
            processed = run_preprocess(scenario_config)
            factors = run_features(scenario_config)
            factor_summary, _, _ = run_factor_evaluate(scenario_config)

            all_universe = processed[["date", "symbol"]].drop_duplicates().copy()
            filtered = apply_filters(factors, scenario_config)
            filtered_universe = filtered.loc[filtered["eligible"], ["date", "symbol"]].drop_duplicates().copy()

            mode_positions: dict[str, pd.DataFrame] = {
                "momentum_top_n_filtered": _positions_momentum_filtered(factors, scenario_config),
                "equal_weight_all": _positions_equal_weight_all(processed),
                "random_top_n_all": _positions_random_top_n(
                    universe=all_universe,
                    top_n=scenario_config.top_n,
                    seed=_seed_for_mode(scenario_config.seed, component, "random_top_n_all"),
                ),
                "random_top_n_filtered": _positions_random_top_n(
                    universe=filtered_universe,
                    top_n=scenario_config.top_n,
                    seed=_seed_for_mode(scenario_config.seed, component, "random_top_n_filtered"),
                ),
            }

            aligned_positions, shared_dates = _align_positions_for_comparison(mode_positions)
            mode_summaries: dict[str, dict] = {
                mode: _run_backtest_from_positions(
                    prices=processed,
                    positions=aligned_positions[mode],
                    config=scenario_config,
                )
                for mode in STRATEGY_MODES
            }

            baseline = mode_summaries["momentum_top_n_filtered"]
            shared_start_date = str(pd.to_datetime(shared_dates[0]).date())
            shared_end_date = str(pd.to_datetime(shared_dates[-1]).date())

            for mode in STRATEGY_MODES:
                backtest_summary = mode_summaries[mode]
                seed_rows.append(
                    {
                        "component": component,
                        "seed": scenario_seed,
                        "strategy_mode": mode,
                        "is_benchmark": mode != "momentum_top_n_filtered",
                        "random_walk_no_drift": scenario_config.random_walk_no_drift,
                        "market_drift": scenario_config.market_drift,
                        "momentum_regime": scenario_config.momentum_regime,
                        "mean_reversion_regime": scenario_config.mean_reversion_regime,
                        "common_start_date": shared_start_date,
                        "common_end_date": shared_end_date,
                        "final_equity": backtest_summary["final_equity"],
                        "total_return": backtest_summary["total_return"],
                        "cagr": backtest_summary["cagr"],
                        "sharpe": backtest_summary["sharpe"],
                        "max_drawdown": backtest_summary["max_drawdown"],
                        "delta_final_equity_vs_momentum": backtest_summary["final_equity"] - baseline["final_equity"],
                        "delta_total_return_vs_momentum": backtest_summary["total_return"] - baseline["total_return"],
                        "delta_cagr_vs_momentum": backtest_summary["cagr"] - baseline["cagr"],
                        "delta_sharpe_vs_momentum": backtest_summary["sharpe"] - baseline["sharpe"],
                        "delta_max_drawdown_vs_momentum": backtest_summary["max_drawdown"] - baseline["max_drawdown"],
                        "valid_samples": factor_summary["valid_samples"],
                        "average_coverage": factor_summary["average_coverage"],
                        "average_ic": factor_summary["average_ic"],
                        "average_rank_ic": factor_summary["average_rank_ic"],
                        "top_bottom_spread": factor_summary["top_bottom_spread"],
                        "factor_turnover": factor_summary["factor_turnover"],
                        "scenario_data_root": str(component_root),
                    }
                )

    by_seed_result = pd.DataFrame(seed_rows)

    if output_csv is None:
        output_csv = experiments_root / "component_test_summary.csv"

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    by_seed_csv = output_csv.with_name(f"{output_csv.stem}_by_seed.csv")
    by_seed_result.to_csv(by_seed_csv, index=False)

    group_cols = [
        "component",
        "strategy_mode",
        "is_benchmark",
        "random_walk_no_drift",
        "market_drift",
        "momentum_regime",
        "mean_reversion_regime",
    ]
    metric_cols = [
        "final_equity",
        "total_return",
        "cagr",
        "sharpe",
        "max_drawdown",
        "delta_final_equity_vs_momentum",
        "delta_total_return_vs_momentum",
        "delta_cagr_vs_momentum",
        "delta_sharpe_vs_momentum",
        "delta_max_drawdown_vs_momentum",
        "valid_samples",
        "average_coverage",
        "average_ic",
        "average_rank_ic",
        "top_bottom_spread",
        "factor_turnover",
    ]

    meta = by_seed_result.groupby(group_cols, as_index=False).agg(
        seed_runs=("seed", "count"),
        common_start_date_min=("common_start_date", "min"),
        common_start_date_max=("common_start_date", "max"),
        common_end_date_min=("common_end_date", "min"),
        common_end_date_max=("common_end_date", "max"),
    )

    means = by_seed_result.groupby(group_cols, as_index=False)[metric_cols].mean()
    means = means.rename(columns={c: f"{c}_mean" for c in metric_cols})

    stds = by_seed_result.groupby(group_cols, as_index=False)[metric_cols].std(ddof=0).fillna(0.0)
    stds = stds.rename(columns={c: f"{c}_std" for c in metric_cols})

    result = meta.merge(means, on=group_cols, how="left").merge(stds, on=group_cols, how="left")

    result.to_csv(output_csv, index=False)
    return result
