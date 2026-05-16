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
