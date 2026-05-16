"""Simple filesystem and serialization helpers."""

# File role: provide shared read/write helpers for parquet and JSON artifacts.

import json
from pathlib import Path

import pandas as pd

from quant.exceptions import EmptyDatasetError


def read_parquet_required(path: Path) -> pd.DataFrame:
    """Read a required parquet artifact.

    Args:
        path: File path to the parquet artifact.

    Returns:
        pd.DataFrame: Loaded dataframe content.

    Raises:
        FileNotFoundError: If the parquet file does not exist.
        EmptyDatasetError: If the parquet file exists but contains no rows.
    """
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    df = pd.read_parquet(path)
    if df.empty:
        raise EmptyDatasetError(f"Dataset is empty: {path}")
    return df


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write a dataframe to parquet.

    Args:
        df: Dataframe to write.
        path: Destination parquet file path.

    Returns:
        None.

    Raises:
        None.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def write_json(payload: dict, path: Path) -> None:
    """Write a dictionary as formatted JSON.

    Args:
        payload: Dictionary payload to serialize.
        path: Destination JSON file path.

    Returns:
        None.

    Raises:
        None.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_json(path: Path) -> dict:
    """Read a JSON file into a dictionary.

    Args:
        path: File path to the JSON artifact.

    Returns:
        dict: Parsed JSON object.

    Raises:
        FileNotFoundError: If the JSON file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
