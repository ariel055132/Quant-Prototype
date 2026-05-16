"""Simple filesystem and serialization helpers."""

import json
from pathlib import Path

import pandas as pd

from quant.exceptions import EmptyDatasetError


def read_parquet_required(path: Path) -> pd.DataFrame:
    """Read a parquet file and fail clearly if it does not exist or is empty."""
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    df = pd.read_parquet(path)
    if df.empty:
        raise EmptyDatasetError(f"Dataset is empty: {path}")
    return df


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write a dataframe to parquet while ensuring parent directories exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def write_json(payload: dict, path: Path) -> None:
    """Write JSON with deterministic formatting for easier diffing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_json(path: Path) -> dict:
    """Read JSON content from disk."""
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
