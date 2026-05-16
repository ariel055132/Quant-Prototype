"""Weekly rebalancing backtest with transaction costs."""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from quant.config import QuantConfig
from quant.exceptions import DataValidationError
from quant.filters.risk import apply_filters
from quant.io_utils import read_parquet_required, write_json, write_parquet
from quant.strategy.selection import select_weekly_positions


def _max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    return float(drawdown.min())


def run_backtest(prices: pd.DataFrame, factors: pd.DataFrame, config: QuantConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Simulate weekly top-N momentum strategy with equal weights."""
    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"])

    filtered = apply_filters(factors, config)
    positions = select_weekly_positions(filtered, config.top_n)
    if positions.empty:
        raise DataValidationError("No eligible weekly positions were selected")

    close_lookup = prices.pivot(index="date", columns="symbol", values="close").sort_index()
    rebalance_dates = sorted(pd.to_datetime(positions["rebalance_date"].unique()))
    if len(rebalance_dates) < 2:
        raise DataValidationError("Need at least two rebalance dates for backtesting")

    equity_rows: list[dict] = []
    trade_rows: list[dict] = []

    equity = config.initial_cash
    prev_weights: dict[str, float] = {}

    for idx in range(len(rebalance_dates) - 1):
        rebalance_date = rebalance_dates[idx]
        next_date = rebalance_dates[idx + 1]

        basket = positions.loc[positions["rebalance_date"] == rebalance_date, ["symbol", "target_weight"]].copy()
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
                "gross_return": gross_return,
                "transaction_cost_rate": cost,
                "net_return": net_return,
                "equity": equity,
            }
        )

        for symbol in all_symbols:
            prev_w = prev_weights.get(symbol, 0.0)
            new_w = current_weights.get(symbol, 0.0)
            if prev_w == new_w:
                continue
            trade_rows.append(
                {
                    "rebalance_date": rebalance_date,
                    "symbol": symbol,
                    "prev_weight": prev_w,
                    "target_weight": new_w,
                    "delta_weight": new_w - prev_w,
                }
            )

        prev_weights = current_weights

    equity_curve = pd.DataFrame(equity_rows)
    trades = pd.DataFrame(trade_rows)

    if equity_curve.empty:
        raise DataValidationError("Equity curve is empty; cannot build summary")

    weekly_returns = equity_curve["net_return"]
    days = (equity_curve["date"].iloc[-1] - rebalance_dates[0]).days
    years = max(days / 365.25, 1 / 52)
    total_return = float(equity_curve["equity"].iloc[-1] / config.initial_cash - 1.0)
    cagr = float((equity_curve["equity"].iloc[-1] / config.initial_cash) ** (1 / years) - 1.0)
    sharpe = float(np.sqrt(52) * weekly_returns.mean() / weekly_returns.std()) if weekly_returns.std() > 0 else 0.0

    summary = {
        "start_date": str(pd.to_datetime(rebalance_dates[0]).date()),
        "end_date": str(pd.to_datetime(equity_curve["date"].iloc[-1]).date()),
        "initial_cash": float(config.initial_cash),
        "final_equity": float(equity_curve["equity"].iloc[-1]),
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": _max_drawdown(equity_curve["equity"]),
        "number_of_trading_days": int(prices["date"].nunique()),
        "rebalance_frequency": config.rebalance_frequency,
        "selected_count_average": float(positions.groupby("rebalance_date")["symbol"].count().mean()),
        "transaction_cost": float(config.transaction_cost),
    }

    return positions, trades, equity_curve, summary


def run(config: QuantConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Execute backtest stage and write portfolio outputs."""
    config.ensure_data_dirs()
    prices = read_parquet_required(config.processed_prices_path)
    factors = read_parquet_required(config.factors_path)

    positions, trades, equity_curve, summary = run_backtest(prices, factors, config)

    write_parquet(positions, config.backtests_dir / "positions.parquet")
    write_parquet(trades, config.backtests_dir / "trades.parquet")
    write_parquet(equity_curve, config.backtests_dir / "equity_curve.parquet")
    write_json(summary, config.backtests_dir / "summary.json")
    return positions, trades, equity_curve, summary
