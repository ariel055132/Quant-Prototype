"""CLI entrypoint for the quant research pipeline."""

# File role: map CLI commands to each pipeline stage runner.

from __future__ import annotations

import argparse

from quant.backtest.run import run as run_backtest
from quant.candidates.export import run as export_candidates
from quant.config import QuantConfig
from quant.data.generate import run as generate_data
from quant.factor_evaluation.evaluate import run as evaluate_factors
from quant.features.build import run as build_features
from quant.preprocess.process import run as process_data
from quant.report.show import run as show_report


def _run_pipeline(config: QuantConfig) -> None:
    """Execute the full pipeline in the required stage order.

    Args:
        config: Runtime configuration shared across all stages.

    Returns:
        None.

    Raises:
        None.
    """
    generate_data(config)
    process_data(config)
    build_features(config)
    evaluate_factors(config)
    run_backtest(config)
    export_candidates(config)


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser and subcommands.

    Args:
        None.

    Returns:
        argparse.ArgumentParser: Configured parser for quant commands.

    Raises:
        None.
    """
    parser = argparse.ArgumentParser(prog="quant", description="Taiwan equity quant research tool")

    subparsers = parser.add_subparsers(dest="group", required=True)

    data_parser = subparsers.add_parser("data")
    data_sub = data_parser.add_subparsers(dest="action", required=True)
    data_sub.add_parser("generate")
    data_sub.add_parser("process")

    features_parser = subparsers.add_parser("features")
    features_sub = features_parser.add_subparsers(dest="action", required=True)
    features_sub.add_parser("build")

    factors_parser = subparsers.add_parser("factors")
    factors_sub = factors_parser.add_subparsers(dest="action", required=True)
    factors_sub.add_parser("evaluate")

    backtest_parser = subparsers.add_parser("backtest")
    backtest_sub = backtest_parser.add_subparsers(dest="action", required=True)
    backtest_sub.add_parser("run")

    candidates_parser = subparsers.add_parser("candidates")
    candidates_sub = candidates_parser.add_subparsers(dest="action", required=True)
    export_parser = candidates_sub.add_parser("export")
    export_parser.add_argument("--date", dest="rebalance_date", default=None)

    report_parser = subparsers.add_parser("report")
    report_sub = report_parser.add_subparsers(dest="action", required=True)
    report_sub.add_parser("show")

    pipeline_parser = subparsers.add_parser("pipeline")
    pipeline_sub = pipeline_parser.add_subparsers(dest="action", required=True)
    pipeline_sub.add_parser("run")

    return parser


def main() -> None:
    """Parse CLI arguments and dispatch to the requested stage command.

    Args:
        None.

    Returns:
        None.

    Raises:
        SystemExit: Raised by argparse on parse or parser error conditions.
    """
    parser = _build_parser()
    args = parser.parse_args()

    config = QuantConfig()

    if args.group == "data" and args.action == "generate":
        generate_data(config)
        return

    if args.group == "data" and args.action == "process":
        process_data(config)
        return

    if args.group == "features" and args.action == "build":
        build_features(config)
        return

    if args.group == "factors" and args.action == "evaluate":
        evaluate_factors(config)
        return

    if args.group == "backtest" and args.action == "run":
        run_backtest(config)
        return

    if args.group == "candidates" and args.action == "export":
        export_candidates(config, rebalance_date=args.rebalance_date)
        return

    if args.group == "report" and args.action == "show":
        show_report(config)
        return

    if args.group == "pipeline" and args.action == "run":
        _run_pipeline(config)
        return

    parser.error("Unknown command")


if __name__ == "__main__":
    main()
