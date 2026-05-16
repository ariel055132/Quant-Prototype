"""Run focused diagnostics for momentum_regime scenario robustness checks."""

# File role: run momentum_regime-only checks for cost impact, horizon alignment, and top-N sensitivity.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from quant.backtest.run import run as run_backtest
from quant.config import QuantConfig
from quant.data.generate import run as run_generate
from quant.factor_evaluation.evaluate import run as run_factor_evaluate
from quant.features.build import run as run_features
from quant.preprocess.process import run as run_preprocess

DEFAULT_TOP_N_VALUES = (3, 5, 10, 20)


def _validated_top_n_values(top_n_values: tuple[int, ...]) -> tuple[int, ...]:
    """Validate top-N sweep values.

    Args:
        top_n_values: Candidate top-N values provided by caller.

    Returns:
        tuple[int, ...]: Deduplicated positive top-N values in ascending order.

    Raises:
        ValueError: If no valid top-N value is available.
    """
    cleaned = sorted({int(v) for v in top_n_values if int(v) > 0})
    if not cleaned:
        raise ValueError("top_n_values must contain at least one positive integer")
    return tuple(cleaned)


def _validated_transaction_costs(
    transaction_cost_values: tuple[float, ...] | None,
    baseline_cost: float,
) -> tuple[float, ...]:
    """Validate transaction cost sweep values and include required checkpoints.

    Args:
        transaction_cost_values: Optional caller-provided cost values.
        baseline_cost: Baseline transaction cost from the runtime config.

    Returns:
        tuple[float, ...]: Deduplicated non-negative costs, always including 0 and baseline.

    Raises:
        ValueError: If any cost is negative.
    """
    if transaction_cost_values is None:
        base_values = [0.0, float(baseline_cost)]
    else:
        base_values = [float(v) for v in transaction_cost_values]
        base_values.extend([0.0, float(baseline_cost)])

    if any(v < 0 for v in base_values):
        raise ValueError("transaction_cost_values cannot contain negatives")

    return tuple(sorted(set(base_values)))


def _momentum_only_config(
    base_config: QuantConfig,
    scenario_root: Path,
    seed: int,
    top_n: int,
    transaction_cost: float,
) -> QuantConfig:
    """Build a scenario config where only momentum_regime is active.

    Args:
        base_config: Base runtime configuration.
        scenario_root: Output root path for this scenario.
        seed: RNG seed for deterministic data generation.
        top_n: Number of holdings to select on rebalance.
        transaction_cost: Transaction cost rate for the backtest.

    Returns:
        QuantConfig: Scenario-specific runtime configuration.

    Raises:
        None.
    """
    return replace(
        base_config,
        data_root=scenario_root,
        seed=int(seed),
        top_n=int(top_n),
        transaction_cost=float(transaction_cost),
        random_walk_no_drift=0.0,
        market_drift=0.0,
        momentum_regime=base_config.momentum_regime,
        mean_reversion_regime=0.0,
    )


def run_momentum_regime_checks(
    base_config: QuantConfig,
    output_csv: Path | None = None,
    n_seeds: int = 3,
    top_n_values: tuple[int, ...] = DEFAULT_TOP_N_VALUES,
    transaction_cost_values: tuple[float, ...] | None = None,
) -> pd.DataFrame:
    """Run momentum_regime-only checks for cost impact and top-N sensitivity.

    Args:
        base_config: Base runtime configuration used as the scenario template.
        output_csv: Optional destination path for by-seed output CSV.
        n_seeds: Number of sequential seeds to evaluate.
        top_n_values: Top-N values to sweep.
        transaction_cost_values: Optional transaction cost values to sweep.

    Returns:
        pd.DataFrame: By-seed scenario results with deltas versus zero-cost baseline.

    Raises:
        ValueError: If n_seeds, top-N values, or cost values are invalid.
    """
    if n_seeds < 1:
        raise ValueError("n_seeds must be at least 1")

    top_n_list = _validated_top_n_values(top_n_values)
    cost_list = _validated_transaction_costs(transaction_cost_values, base_config.transaction_cost)
    baseline_cost = float(base_config.transaction_cost)

    if output_csv is None:
        output_csv = base_config.data_root / "experiments" / "momentum_regime_checks" / "momentum_regime_checks_by_seed.csv"

    rows: list[dict] = []
    experiments_root = output_csv.parent

    for seed_idx in range(n_seeds):
        scenario_seed = base_config.seed + seed_idx
        for top_n in top_n_list:
            for transaction_cost in cost_list:
                cost_tag = f"{transaction_cost:.6f}".replace(".", "p")
                scenario_root = (
                    experiments_root
                    / f"seed_{scenario_seed}"
                    / f"top_n_{top_n}"
                    / f"cost_{cost_tag}"
                )
                scenario_config = _momentum_only_config(
                    base_config=base_config,
                    scenario_root=scenario_root,
                    seed=scenario_seed,
                    top_n=top_n,
                    transaction_cost=transaction_cost,
                )

                run_generate(scenario_config)
                run_preprocess(scenario_config)
                run_features(scenario_config)
                factor_summary, _, _ = run_factor_evaluate(scenario_config)
                _, _, _, backtest_summary = run_backtest(scenario_config)

                rows.append(
                    {
                        "seed": scenario_seed,
                        "top_n": int(top_n),
                        "transaction_cost": float(transaction_cost),
                        "start_date": backtest_summary["start_date"],
                        "end_date": backtest_summary["end_date"],
                        "final_equity": backtest_summary["final_equity"],
                        "total_return": backtest_summary["total_return"],
                        "cagr": backtest_summary["cagr"],
                        "sharpe": backtest_summary["sharpe"],
                        "max_drawdown": backtest_summary["max_drawdown"],
                        "valid_samples": factor_summary["valid_samples"],
                        "average_coverage": factor_summary["average_coverage"],
                        "average_ic": factor_summary["average_ic"],
                        "average_rank_ic": factor_summary["average_rank_ic"],
                        "top_bottom_spread": factor_summary["top_bottom_spread"],
                        "factor_turnover": factor_summary["factor_turnover"],
                        "evaluation_horizon": factor_summary.get("evaluation_horizon", "unknown"),
                        "scenario_data_root": str(scenario_root),
                    }
                )

    result = pd.DataFrame(rows)

    cost0_cols = [
        "final_equity",
        "total_return",
        "cagr",
        "sharpe",
        "max_drawdown",
    ]
    cost0 = result.loc[result["transaction_cost"] == 0.0, ["seed", "top_n", *cost0_cols]].copy()
    cost0 = cost0.rename(columns={c: f"{c}_cost0" for c in cost0_cols})

    result = result.merge(cost0, on=["seed", "top_n"], how="left")
    for c in cost0_cols:
        result[f"delta_{c}_vs_cost0"] = result[c] - result[f"{c}_cost0"]

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_csv, index=False)

    summary_metrics = [
        "final_equity",
        "total_return",
        "cagr",
        "sharpe",
        "max_drawdown",
        "delta_final_equity_vs_cost0",
        "delta_total_return_vs_cost0",
        "delta_cagr_vs_cost0",
        "delta_sharpe_vs_cost0",
        "delta_max_drawdown_vs_cost0",
        "average_ic",
        "average_rank_ic",
        "top_bottom_spread",
        "factor_turnover",
    ]

    summary = result.groupby(["top_n", "transaction_cost"], as_index=False).agg(
        seed_runs=("seed", "count"),
        evaluation_horizon=("evaluation_horizon", "first"),
    )

    means = result.groupby(["top_n", "transaction_cost"], as_index=False)[summary_metrics].mean()
    means = means.rename(columns={c: f"{c}_mean" for c in summary_metrics})

    stds = result.groupby(["top_n", "transaction_cost"], as_index=False)[summary_metrics].std(ddof=0).fillna(0.0)
    stds = stds.rename(columns={c: f"{c}_std" for c in summary_metrics})

    summary = summary.merge(means, on=["top_n", "transaction_cost"], how="left")
    summary = summary.merge(stds, on=["top_n", "transaction_cost"], how="left")

    baseline_rows = summary.loc[summary["transaction_cost"] == baseline_cost].copy()
    baseline_rows = baseline_rows.rename(
        columns={
            "delta_total_return_vs_cost0_mean": "cost_impact_total_return_mean",
            "delta_sharpe_vs_cost0_mean": "cost_impact_sharpe_mean",
            "delta_cagr_vs_cost0_mean": "cost_impact_cagr_mean",
        }
    )
    summary = summary.merge(
        baseline_rows[["top_n", "cost_impact_total_return_mean", "cost_impact_sharpe_mean", "cost_impact_cagr_mean"]],
        on="top_n",
        how="left",
    )

    summary_csv = output_csv.with_name(f"{output_csv.stem}_summary.csv")
    summary.to_csv(summary_csv, index=False)
    return result
