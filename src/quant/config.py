"""Configuration for the quant research pipeline."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class QuantConfig:
    """Runtime configuration with safe defaults for Version 1."""

    data_root: Path = Path("data")
    seed: int = 42
    start_date: str = "2020-01-01"
    end_date: str = "2024-12-31"
    symbols: tuple[str, ...] = (
        "1101",
        "1216",
        "1301",
        "2002",
        "2303",
        "2317",
        "2327",
        "2330",
        "2454",
        "2603",
        "2882",
        "2891",
    )
    top_n: int = 10
    initial_cash: float = 1_000_000.0
    transaction_cost: float = 0.001
    volatility_threshold: float = 0.60
    min_avg_volume: float = 500_000.0
    min_factor_samples: int = 30
    rebalance_frequency: str = "weekly"

    @property
    def raw_prices_path(self) -> Path:
        return self.data_root / "raw" / "prices.parquet"

    @property
    def processed_prices_path(self) -> Path:
        return self.data_root / "processed" / "prices.parquet"

    @property
    def factors_path(self) -> Path:
        return self.data_root / "features" / "factors.parquet"

    @property
    def factor_eval_dir(self) -> Path:
        return self.data_root / "factor_evaluation"

    @property
    def signals_dir(self) -> Path:
        return self.data_root / "signals"

    @property
    def backtests_dir(self) -> Path:
        return self.data_root / "backtests"

    def ensure_data_dirs(self) -> None:
        (self.data_root / "raw").mkdir(parents=True, exist_ok=True)
        (self.data_root / "processed").mkdir(parents=True, exist_ok=True)
        (self.data_root / "features").mkdir(parents=True, exist_ok=True)
        self.factor_eval_dir.mkdir(parents=True, exist_ok=True)
        self.signals_dir.mkdir(parents=True, exist_ok=True)
        self.backtests_dir.mkdir(parents=True, exist_ok=True)
