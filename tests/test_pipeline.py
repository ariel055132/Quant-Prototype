from quant.backtest.run import run as run_backtest
from quant.candidates.export import run as export_candidates
from quant.config import QuantConfig
from quant.data.generate import run as generate_data
from quant.factor_evaluation.evaluate import run as evaluate_factors
from quant.features.build import run as build_features
from quant.preprocess.process import run as process_data


def test_pipeline_writes_expected_outputs(tmp_path) -> None:
    config = QuantConfig(
        data_root=tmp_path / "data",
        seed=5,
        start_date="2022-01-03",
        end_date="2023-12-29",
        symbols=("2330", "2317", "2454", "2303", "2603"),
        min_factor_samples=10,
        top_n=3,
    )

    generate_data(config)
    process_data(config)
    build_features(config)
    evaluate_factors(config)
    run_backtest(config)
    export_candidates(config)

    assert config.raw_prices_path.exists()
    assert config.processed_prices_path.exists()
    assert config.factors_path.exists()
    assert (config.factor_eval_dir / "momentum_score_summary.json").exists()
    assert (config.factor_eval_dir / "momentum_score_ic.parquet").exists()
    assert (config.factor_eval_dir / "momentum_score_quantiles.parquet").exists()
    assert (config.backtests_dir / "positions.parquet").exists()
    assert (config.backtests_dir / "trades.parquet").exists()
    assert (config.backtests_dir / "equity_curve.parquet").exists()
    assert (config.backtests_dir / "summary.json").exists()
    assert (config.signals_dir / "weekly_candidates.parquet").exists()
