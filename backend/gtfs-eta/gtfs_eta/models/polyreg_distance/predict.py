"""
Prediction interface for the Polynomial Regression Distance model.

Ported from eta_prediction/models/polyreg_distance/predict.py on branch
feature/eta_prediction with the following changes:
  - sys.path hacks removed.
  - Imports rewritten to absolute gtfs_eta.* paths.
"""

from typing import Dict, Optional

import pandas as pd

from gtfs_eta.models.common.registry import get_registry
from gtfs_eta.models.common.utils import format_seconds


def predict_eta(
    model_key: str,
    distance_to_stop: float,
    route_id: Optional[str] = None,
) -> Dict:
    """
    Predict ETA using a polynomial regression distance model.

    Args:
        model_key: Model identifier in the registry.
        distance_to_stop: Distance to the stop in metres.
        route_id: Route ID — required for route-specific models.

    Returns:
        Dict with eta_seconds, eta_minutes, eta_formatted, model_key,
        model_type, distance_to_stop_m, route_specific, degree, coefficients.
    """
    registry = get_registry()
    model = registry.load_model(model_key)
    metadata = registry.load_metadata(model_key)

    input_data: Dict = {"distance_to_stop": [distance_to_stop]}
    if model.route_specific:
        if route_id is None:
            raise ValueError("route_id is required for a route-specific model")
        input_data["route_id"] = [route_id]

    input_df = pd.DataFrame(input_data)
    eta_seconds = float(model.predict(input_df)[0])

    coefs = model.get_coefficients(route_id if model.route_specific else None)

    return {
        "eta_seconds": eta_seconds,
        "eta_minutes": eta_seconds / 60.0,
        "eta_formatted": format_seconds(eta_seconds),
        "model_key": model_key,
        "model_type": "polyreg_distance",
        "distance_to_stop_m": distance_to_stop,
        "route_specific": metadata.get("route_specific", False),
        "degree": metadata.get("degree"),
        "coefficients": coefs,
    }
