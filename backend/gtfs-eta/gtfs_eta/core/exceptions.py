"""Custom exceptions for gtfs_eta."""


class GTFSEtaError(Exception):
    """Base error for the gtfs_eta package."""


class ModelNotFoundError(GTFSEtaError):
    """Raised when a requested model is not in the registry."""


class PredictionError(GTFSEtaError):
    """Raised when a model prediction fails."""
