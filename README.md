# Quant Prototype

A modular Python research-tool scaffold for Taiwan equity-style quant experiments using synthetic data only.

## Version 1 Scope

- Synthetic data generation (no network access)
- Data preprocessing and validation
- Price-based factor engineering
- Factor effectiveness evaluation
- Weekly momentum plus risk-filter strategy backtest
- Weekly candidate export for manual review
- CLI entrypoints for each stage and full pipeline

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Run the full pipeline:

```bash
quant pipeline run
```

Run stages independently:

```bash
quant data generate
quant data process
quant features build
quant factors evaluate
quant backtest run
quant candidates export
quant report show
quant experiments component-test
```

## Data Outputs

The pipeline writes outputs under `data/`:

- `data/raw/prices.parquet`
- `data/processed/prices.parquet`
- `data/features/factors.parquet`
- `data/factor_evaluation/momentum_score_summary.json`
- `data/factor_evaluation/momentum_score_ic.parquet`
- `data/factor_evaluation/momentum_score_quantiles.parquet`
- `data/backtests/positions.parquet`
- `data/backtests/trades.parquet`
- `data/backtests/equity_curve.parquet`
- `data/backtests/summary.json`
- `data/signals/weekly_candidates.parquet`

## Podman Usage

Build the runtime image from `Containerfile`:

```bash
podman build -f Containerfile --target base -t localhost/quant-prototype:latest .
```

Run the full pipeline in a disposable container:

```bash
podman run --rm -v "$(pwd)":/app localhost/quant-prototype:latest
```

Run tests in a container:

```bash
podman build -f Containerfile --target test -t localhost/quant-prototype:test .
podman run --rm -v "$(pwd)":/app localhost/quant-prototype:test
```

Show strategy and factor summary after running the pipeline:

```bash
podman run --rm -v "$(pwd)":/app localhost/quant-prototype:latest quant report show
```

Use Podman Compose:

```bash
podman-compose -f podman-compose.yml run --rm quant
podman-compose -f podman-compose.yml run --rm quant-test
podman-compose -f podman-compose.yml run --rm quant-shell
```

## Daily Workflow With Make

Use the included Makefile for one-command execution:

```bash
make build
make test
make pipeline
make shell
```

`make build` and `make test` automatically remove old `quant-prototype` images before building again.

## Continue Testing With Podman

For regular development, this loop is recommended:

1. Rebuild and run tests after code changes:

```bash
make test
```

2. Run the full pipeline and validate artifacts under `data/`:

```bash
make pipeline
```

3. Open a container shell for manual checks:

```bash
make shell
```

4. Optional compose-based test run:

```bash
podman-compose -f podman-compose.yml run --rm quant-test
```

## Component-By-Component Synthetic Tests

Run isolated tests where only one synthetic return component is active at a time:

```bash
quant experiments component-test
```

Run multiple seeds per scenario (recommended):

```bash
quant experiments component-test --seeds 5
```

The command writes a consolidated CSV by default:

- `data/experiments/component_tests/component_test_summary.csv`
- `data/experiments/component_tests/component_test_summary_by_seed.csv`

`component_test_summary.csv` contains aggregated statistics (`*_mean`, `*_std`) across seeds,
while `component_test_summary_by_seed.csv` keeps one row per component + mode + seed.

Each component now includes four strategy scenarios:

- `momentum_top_n_filtered` (main strategy)
- `equal_weight_all` (benchmark)
- `random_top_n_all` (benchmark)
- `random_top_n_filtered` (benchmark)

The CSV also includes comparison columns against the momentum strategy:

- `delta_final_equity_vs_momentum`
- `delta_total_return_vs_momentum`
- `delta_cagr_vs_momentum`
- `delta_sharpe_vs_momentum`
- `delta_max_drawdown_vs_momentum`

Within each component + seed run, all strategy modes are aligned to the same shared rebalance window before backtest,
so benchmark comparisons start from the same date.

To write to a custom CSV path:

```bash
quant experiments component-test --output-csv data/experiments/my_component_results.csv
```

When `--output-csv` is provided, the by-seed file is also written next to it using the `_by_seed.csv` suffix.

## Momentum-Regime Focused Checks

Run focused checks only for `momentum_regime` to verify cost impact and top-N sensitivity:

```bash
quant experiments momentum-regime-check --seeds 3 --top-n-values 3 5 10 20
```

This command automatically includes `transaction_cost=0` and the configured baseline transaction cost,
and writes:

- `data/experiments/momentum_regime_checks/momentum_regime_checks_by_seed.csv`
- `data/experiments/momentum_regime_checks/momentum_regime_checks_by_seed_summary.csv`

You can override transaction costs explicitly:

```bash
quant experiments momentum-regime-check --transaction-costs 0 0.001
```
