# Personal Taiwan Equity Quant Research Tool Design

## 1. Purpose

This document defines the first version of a personal Taiwan equity quant research tool. It is intended for coding agents or engineers who will implement the system.

The system is a research and decision-support tool, not an automated trading platform. It should help the user evaluate strategy quality, monitor factor effectiveness, and export weekly candidate stocks for manual review. Final trading decisions and order placement remain manual.

## 2. Product Direction

Version 1 should be a research-tool standard version:

- Use synthetic Taiwan-equity-style data to run the full research pipeline.
- Prioritize performance reports over live candidate generation.
- Also export weekly candidate stock lists for manual review.
- Use weekly rebalancing by default.
- Implement a momentum plus risk-filter strategy.
- Preserve future extension space for multi-factor research, including market, size, value, and momentum factors.

Version 1 must not include:

- Automated order placement.
- Broker API integration.
- Real-time market data.
- High-frequency trading.
- Real-money position management.
- Web dashboard.
- Paid or external data sources.

## 3. Core Pipeline

The Version 1 pipeline is:

```text
Generate Data
-> Preprocess Data
-> Build Factors
-> Evaluate Factors
-> Apply Filters
-> Run Weekly Backtest
-> Generate Performance Report
-> Export Weekly Candidates
```

Each stage should be callable independently from the CLI. A full pipeline command should also be available.

## 4. Architecture

The codebase should be modular and easy for future agents to extend.

Suggested modules:

- `data`: Generate synthetic Taiwan-equity-style OHLCV data. In the future, this module can be extended or replaced with real data ingestion.
- `preprocess`: Clean raw OHLCV data, parse dates, sort records, remove duplicates, and validate basic price and volume fields.
- `features`: Compute price-based factors such as returns, moving averages, volatility, average volume, and momentum score.
- `factor_evaluation`: Evaluate factor effectiveness before the factor is used by the strategy.
- `filters`: Apply risk and liquidity filters, such as high-volatility exclusion and low-volume exclusion.
- `strategy`: Convert factor values and filter results into weekly target positions.
- `backtest`: Simulate weekly rebalancing, transaction costs, positions, trades, and equity curve.
- `report`: Display performance summaries and factor evaluation summaries.
- `candidates`: Export weekly candidate stocks for manual review.

The system should not hard-code `momentum_score` as the only possible strategy input. Version 1 uses `momentum_score`, but the design should allow additional factors to be added later.

## 5. Data Layout

Use local Parquet and JSON files.

Recommended directory structure:

```text
data/
  raw/
    prices.parquet
  processed/
    prices.parquet
  features/
    factors.parquet
  factor_evaluation/
    momentum_score_summary.json
    momentum_score_ic.parquet
    momentum_score_quantiles.parquet
  signals/
    weekly_candidates.parquet
  backtests/
    positions.parquet
    trades.parquet
    equity_curve.parquet
    summary.json
```

Layer meanings:

- `raw`: Synthetic or future imported data, preserved as close to source form as practical.
- `processed`: Cleaned OHLCV data used as the shared input for research modules.
- `features`: Per-symbol, per-date factor values.
- `factor_evaluation`: Factor diagnostics that monitor whether factors are useful and stable.
- `signals`: Weekly candidate stock lists for manual review.
- `backtests`: Positions, trades, equity curve, and performance summary.

## 6. Synthetic Data Requirements

Version 1 uses synthetic data only. It must not require network access or external APIs.

Synthetic daily OHLCV data should include:

- `date`: Trading date.
- `symbol`: Stock code, such as `2330`, `2317`, or `2454`.
- `open`: Open price.
- `high`: High price.
- `low`: Low price.
- `close`: Close price.
- `volume`: Trading volume.

Requirements:

- Include multiple stocks.
- Include multiple trading days.
- Prices must be positive.
- Volume must be non-negative.
- `date + symbol` must be unique.
- A fixed seed must reproduce the same data.
- Data should be long enough to support 20-day and 60-day factors plus weekly backtesting.

## 7. Preprocessing Requirements

The preprocessing stage should:

- Convert `date` to a date or datetime type.
- Sort by `symbol` and `date`.
- Remove duplicate `date + symbol` rows.
- Validate that OHLC prices are positive.
- Validate that `high >= low`.
- Validate that `volume >= 0`.
- Write cleaned data to `data/processed/prices.parquet`.

Missing required columns, invalid dates, invalid prices, or impossible OHLC relationships should stop the command with a clear error message.

## 8. Factor Engineering

Version 1 should compute price-based factors only. These factors are the practical Version 1 equivalent of a simplified UMD-style momentum signal.

Recommended factor columns:

- `return_20d`: 20-day return.
- `return_60d`: 60-day return.
- `ma_20`: 20-day moving average.
- `volatility_20d`: 20-day return volatility.
- `avg_volume_20d`: 20-day average volume.
- `momentum_score`: Combined momentum score.

Factor requirements:

- All rolling calculations must be grouped by `symbol`.
- Rolling factors must not use future data.
- Early-window null values are allowed.
- Factor output should preserve `date` and `symbol`.
- Output should be written to `data/features/factors.parquet`.

Suggested first-pass `momentum_score`:

```text
momentum_score = weighted combination of return_20d and return_60d, adjusted by volatility_20d
```

The exact formula can be simple in Version 1, but it should be documented in code and tests.

## 9. Factor Evaluation

After building factors and before applying strategy filters, the system should evaluate factor effectiveness.

The purpose of this stage is to monitor whether a factor is useful, stable, and safe to use in a strategy. It should not directly place trades.

Version 1 should evaluate `momentum_score`. The design should allow future factors such as `size_score`, `value_score`, `quality_score`, `mkt_excess_return`, `SMB`, `HML`, and `UMD` to use the same evaluation framework.

Recommended metrics:

- `factor_coverage`: Number and percentage of stocks with valid factor values per date.
- `ic`: Correlation between factor value and next-period return.
- `rank_ic`: Rank correlation between factor rank and next-period return rank.
- `top_bottom_spread`: Average future return of high-score group minus low-score group.
- `quantile_returns`: Future returns by factor quantile.
- `factor_turnover`: Weekly turnover of the high-score group.

Recommended outputs:

- `data/factor_evaluation/momentum_score_summary.json`
- `data/factor_evaluation/momentum_score_ic.parquet`
- `data/factor_evaluation/momentum_score_quantiles.parquet`

Error handling:

- If a factor is entirely null, stop that factor evaluation and report the reason.
- If there are too few valid samples, stop that factor evaluation and report the reason.
- Rolling-window null values should be reflected in coverage rather than treated as errors.

The performance report should include a short factor evaluation summary, so the user can tell whether strategy performance is related to factor quality.

## 10. Strategy Logic

Version 1 should implement a momentum plus risk-filter strategy.

The strategy includes the simplified momentum strategy, then adds practical filters for manual trading.

Strategy flow:

```text
Processed prices
-> Price-based factors
-> Factor evaluation
-> Risk and liquidity filters
-> Rank eligible stocks by momentum_score
-> Select top N stocks
-> Build equal-weight weekly portfolio
-> Backtest performance
-> Export latest or specified weekly candidates
```

Recommended filters:

- Exclude stocks with missing `momentum_score`.
- Exclude stocks with `volatility_20d` above a configured threshold.
- Exclude stocks with `avg_volume_20d` below a configured threshold.
- Exclude stocks with invalid or abnormal price records from preprocessing.

If fewer than N stocks pass filters, the strategy should continue with the available stocks and report the actual selected count.

## 11. Rebalancing

The default rebalancing frequency is weekly.

Rationale:

- More practical for manual review than daily rebalancing.
- Produces more research samples than monthly rebalancing.
- Fits the user's preference for human-controlled order placement.

The design should preserve future support for daily or monthly rebalancing, but Version 1 should default to weekly.

## 12. Backtesting

The backtest should:

- Use weekly rebalancing by default.
- Rank eligible stocks using `momentum_score`.
- Select the top N stocks.
- Allocate equal weight across selected stocks.
- Use future returns only after the signal date.
- Avoid look-ahead bias.
- Support initial cash.
- Support transaction cost.
- Output positions, trades, equity curve, and summary.

Recommended outputs:

- `data/backtests/positions.parquet`
- `data/backtests/trades.parquet`
- `data/backtests/equity_curve.parquet`
- `data/backtests/summary.json`

Minimum summary fields:

- `start_date`
- `end_date`
- `initial_cash`
- `final_equity`
- `total_return`
- `cagr`
- `sharpe`
- `max_drawdown`
- `number_of_trading_days`
- `rebalance_frequency`
- `selected_count_average`
- `transaction_cost`

If the equity curve is empty, the command should stop instead of writing a misleading summary.

## 13. Candidate Export

The system should export weekly candidate stock lists for manual review.

Candidate output should include:

- `rebalance_date`
- `symbol`
- `rank`
- `momentum_score`
- `return_20d`
- `return_60d`
- `volatility_20d`
- `avg_volume_20d`
- Filter pass or fail status when useful.

The default candidate export can use the latest available rebalance date. It should also support exporting candidates for a specified date later if needed.

Candidates are not orders. The file is a research output for manual review.

## 14. CLI

Recommended CLI commands:

```bash
quant data generate
quant data process
quant features build
quant factors evaluate
quant backtest run
quant candidates export
quant report show
quant pipeline run
```

Command responsibilities:

- `quant data generate`: Generate synthetic raw price data.
- `quant data process`: Clean raw price data.
- `quant features build`: Build price-based factors.
- `quant factors evaluate`: Evaluate factor effectiveness.
- `quant backtest run`: Run the weekly momentum plus risk-filter backtest.
- `quant candidates export`: Export weekly candidate stocks.
- `quant report show`: Display strategy performance and factor summary.
- `quant pipeline run`: Run the full pipeline in order.

All output paths should have reasonable defaults.

## 15. Error Handling Principles

Use clear, research-tool-friendly errors.

Stop immediately for:

- Missing required columns.
- Invalid dates.
- Non-positive OHLC prices.
- `high < low`.
- Negative volume.
- Empty processed dataset.
- Empty factor dataset.
- Entirely null target factor.
- Too few valid samples for factor evaluation.
- Empty equity curve.

Allow but report:

- Rolling-window nulls.
- Fewer candidates than requested.
- Dates with incomplete factor coverage.

## 16. Testing Requirements

Version 1 tests should focus on preventing common quant research mistakes.

Required tests:

- Synthetic data generation is reproducible with the same seed.
- Synthetic data contains multiple symbols, multiple dates, and required columns.
- Preprocessing removes duplicate `date + symbol` records.
- Preprocessing rejects invalid OHLCV data.
- Factor calculations are grouped by `symbol`.
- Rolling factors do not use future data.
- Factor evaluation generates IC, rank IC, quantile returns, and summary output.
- Risk and liquidity filters exclude ineligible stocks.
- Weekly rebalance dates are generated correctly.
- Backtest deducts transaction costs.
- Backtest produces non-empty equity curve when valid inputs exist.
- Summary includes `final_equity`, `cagr`, `sharpe`, and `max_drawdown`.
- Candidate export returns the latest or specified rebalance date candidates.

## 17. Future Multi-Factor Extension Space

Version 1 should not implement full Fama-French or Carhart factors because that would require additional data and careful point-in-time handling.

Future factors may include:

- `MKT`: Market excess return or benchmark return.
- `SMB`: Small-size portfolio minus large-size portfolio.
- `HML`: High book-to-market portfolio minus low book-to-market portfolio.
- `UMD`: High-momentum portfolio minus low-momentum portfolio.
- `size_score`: Single-stock size factor.
- `value_score`: Single-stock valuation factor.
- `quality_score`: Single-stock quality factor.

Important note for future `HML`:

- Traditional HML uses high book-to-market minus low book-to-market.
- In P/B terms, this is roughly low P/B value stocks minus high P/B growth stocks.
- A high-P/B-minus-low-P/B definition would reverse the traditional direction.

Future multi-factor implementation will require:

- Market index or benchmark data.
- Market capitalization data.
- Book value or P/B data.
- Point-in-time financial statement availability.
- Explicit handling of data release dates to avoid look-ahead bias.

The Version 1 interface should make future extension possible by treating factors as named columns and using generic evaluation and scoring concepts, not one-off hard-coded logic.

## 18. Implementation Priorities

Implementation should prioritize:

1. A complete reproducible pipeline over strategy complexity.
2. Clear data contracts between stages.
3. Avoiding look-ahead bias.
4. Focused tests around data quality, factor correctness, factor evaluation, and backtest integrity.
5. Simple code that future AI agents can safely extend.

Version 1 is complete when:

- The full pipeline runs without external data.
- The system produces factor evaluation outputs.
- The system produces a weekly backtest performance summary.
- The system exports weekly candidate stocks.
- Tests verify the main research and backtest assumptions.
