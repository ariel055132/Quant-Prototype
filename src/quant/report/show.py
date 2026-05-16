"""Terminal report output for performance and factor diagnostics."""

from __future__ import annotations

from quant.config import QuantConfig
from quant.io_utils import read_json


def build_report(config: QuantConfig) -> dict:
    """Collect backtest and factor-evaluation summaries for display."""
    performance = read_json(config.backtests_dir / "summary.json")
    factor = read_json(config.factor_eval_dir / "momentum_score_summary.json")
    return {"performance": performance, "factor": factor}


def run(config: QuantConfig) -> dict:
    """Execute report stage and print concise summaries."""
    payload = build_report(config)
    perf = payload["performance"]
    fac = payload["factor"]

    print("Performance Summary")
    print(f"  Date Range: {perf['start_date']} -> {perf['end_date']}")
    print(f"  Final Equity: {perf['final_equity']:.2f}")
    print(f"  Total Return: {perf['total_return']:.4f}")
    print(f"  CAGR: {perf['cagr']:.4f}")
    print(f"  Sharpe: {perf['sharpe']:.4f}")
    print(f"  Max Drawdown: {perf['max_drawdown']:.4f}")

    print("Factor Summary")
    print(f"  Factor: {fac['factor']}")
    print(f"  Valid Samples: {fac['valid_samples']}")
    print(f"  Average Coverage: {fac['average_coverage']:.4f}")
    print(f"  Average IC: {fac['average_ic']:.4f}")
    print(f"  Average Rank IC: {fac['average_rank_ic']:.4f}")
    print(f"  Top-Bottom Spread: {fac['top_bottom_spread']:.6f}")
    print(f"  Factor Turnover: {fac['factor_turnover']:.4f}")

    return payload
