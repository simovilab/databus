"""
Utility functions for gtfs_eta.models.

Ported from eta_prediction/models/common/utils.py on branch
feature/eta_prediction.  Training helpers (print_metrics_table,
train_test_summary, create_feature_importance_df) are retained as-is;
they are harmless at inference time.
"""

import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
import logging


def setup_logging(name: str = "eta_models", level: str = "INFO") -> logging.Logger:
    """Setup consistent logging for models."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)
    return logger


def safe_divide(
    numerator: np.ndarray,
    denominator: np.ndarray,
    fill_value: float = 0.0,
) -> np.ndarray:
    """Safe division that handles division by zero."""
    result = np.full_like(numerator, fill_value, dtype=float)
    mask = denominator != 0
    result[mask] = numerator[mask] / denominator[mask]
    return result


def clip_predictions(
    predictions: np.ndarray,
    min_value: float = 0.0,
    max_value: float = 7200.0,
) -> np.ndarray:
    """Clip predictions to reasonable range (0–7200 s by default)."""
    return np.clip(predictions, min_value, max_value)


def calculate_speed_kmh(distance_m: float, time_s: float) -> float:
    """Calculate speed in km/h from distance and time."""
    if time_s <= 0:
        return 0.0
    return (distance_m / 1000) / (time_s / 3600)


def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Calculate great-circle distance between two points (meters)."""
    R = 6_371_000
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)
    a = (
        np.sin(delta_phi / 2) ** 2
        + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
    )
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c


def format_seconds(seconds: float) -> str:
    """Format seconds as human-readable string (e.g. '2m 30s', '1h 15m')."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"


def add_lag_features(
    df: pd.DataFrame,
    columns: List[str],
    lags: List[int],
    group_by: Optional[str] = None,
) -> pd.DataFrame:
    """Add lagged features to dataframe (returns a new copy)."""
    df_copy = df.copy()
    for col in columns:
        for lag in lags:
            lag_col_name = f"{col}_lag{lag}"
            if group_by:
                df_copy[lag_col_name] = df_copy.groupby(group_by)[col].shift(lag)
            else:
                df_copy[lag_col_name] = df_copy[col].shift(lag)
    return df_copy


def smooth_predictions(
    predictions: np.ndarray,
    window_size: int = 3,
    method: str = "ewma",
    alpha: float = 0.3,
) -> np.ndarray:
    """Smooth predictions using rolling average or EWMA."""
    if len(predictions) < window_size:
        return predictions
    s = pd.Series(predictions)
    if method == "mean":
        return s.rolling(window_size, min_periods=1).mean().values
    elif method == "median":
        return s.rolling(window_size, min_periods=1).median().values
    elif method == "ewma":
        return s.ewm(alpha=alpha).mean().values
    else:
        raise ValueError(f"Unknown smoothing method: {method}")
