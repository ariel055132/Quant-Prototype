"""Project-specific exceptions."""

# File role: define custom exception types used across the pipeline.


class QuantError(RuntimeError):
    """Base exception for quant pipeline failures."""


class DataValidationError(QuantError):
    """Raised when a dataset violates required data contracts."""


class EmptyDatasetError(QuantError):
    """Raised when a required dataset is unexpectedly empty."""
