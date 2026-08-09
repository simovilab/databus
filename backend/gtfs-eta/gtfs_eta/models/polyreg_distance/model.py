"""
PolyRegDistanceModel — inference-only class.

Extracted verbatim from eta_prediction/models/polyreg_distance/train.py on
branch feature/eta_prediction.  Only the class and its sklearn/numpy/pandas
imports are present here — training functions, dataset loaders, metrics, and
ModelKey helpers are deliberately excluded so pickles can be loaded without
any training-time dependency.

Stable import path for pickle compatibility:
    gtfs_eta.models.polyreg_distance.model.PolyRegDistanceModel
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures
from typing import Dict, Optional

from gtfs_eta.models.common.utils import clip_predictions


class PolyRegDistanceModel:
    """
    Polynomial regression on distance with optional route-specific models.

    Features: distance_to_stop, (distance)^2, (distance)^3, ...
    Can fit separate models per route for better performance.
    """

    def __init__(
        self,
        degree: int = 2,
        alpha: float = 1.0,
        route_specific: bool = False,
    ):
        """
        Args:
            degree: Polynomial degree (1, 2, or 3 recommended)
            alpha: Ridge regression alpha (regularization strength)
            route_specific: Whether to fit separate model per route
        """
        self.degree = degree
        self.alpha = alpha
        self.route_specific = route_specific
        self.models: Dict[str, Pipeline] = {}  # route_id -> fitted pipeline
        self.global_model: Optional[Pipeline] = None
        self.feature_cols = ["distance_to_stop"]

    # ── internal ──────────────────────────────────────────────────────────────

    def _create_pipeline(self) -> Pipeline:
        return Pipeline(
            [
                ("poly", PolynomialFeatures(degree=self.degree, include_bias=True)),
                ("ridge", Ridge(alpha=self.alpha)),
            ]
        )

    # ── public API ────────────────────────────────────────────────────────────

    def fit(
        self,
        train_df: pd.DataFrame,
        target_col: str = "time_to_arrival_seconds",
    ) -> "PolyRegDistanceModel":
        """
        Train model(s).

        Args:
            train_df: DataFrame with at least 'distance_to_stop' and target_col.
                      Also needs 'route_id' when route_specific=True.
            target_col: Name of the target column.

        Returns:
            self (for chaining)
        """
        if "distance_to_stop" not in train_df.columns:
            raise ValueError("'distance_to_stop' column required in train_df")

        if self.route_specific:
            for route_id, route_df in train_df.groupby("route_id"):
                X = route_df[["distance_to_stop"]].values
                y = route_df[target_col].values
                model = self._create_pipeline()
                model.fit(X, y)
                self.models[route_id] = model
        else:
            X = train_df[["distance_to_stop"]].values
            y = train_df[target_col].values
            self.global_model = self._create_pipeline()
            self.global_model.fit(X, y)

        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict ETAs (seconds).

        Args:
            X: DataFrame with 'distance_to_stop' (and 'route_id' when route_specific).

        Returns:
            1-D numpy array of predicted ETAs, clipped to [0, 7200] seconds.
        """
        if self.route_specific:
            if "route_id" not in X.columns:
                raise ValueError("'route_id' required for route-specific model")

            predictions = np.zeros(len(X))
            X_reset = X.reset_index(drop=True)

            for route_id, route_df in X_reset.groupby("route_id"):
                pos_indices = route_df.index.values
                X_route = route_df[["distance_to_stop"]].values

                if route_id in self.models:
                    predictions[pos_indices] = self.models[route_id].predict(X_route)
                elif self.global_model is not None:
                    predictions[pos_indices] = self.global_model.predict(X_route)
                else:
                    # fallback: rough 30 km/h
                    predictions[pos_indices] = X_route.flatten() / 30_000 * 3_600
        else:
            if self.global_model is None:
                raise ValueError("Model has not been trained — call fit() first")
            X_dist = X[["distance_to_stop"]].values
            predictions = self.global_model.predict(X_dist)

        return clip_predictions(predictions)

    def get_coefficients(self, route_id: Optional[str] = None) -> Dict:
        """
        Return ridge coefficients for the given route (or the global model).
        """
        if route_id and route_id in self.models:
            model = self.models[route_id]
        elif self.global_model:
            model = self.global_model
        else:
            return {}

        coefs = model.named_steps["ridge"].coef_
        intercept = model.named_steps["ridge"].intercept_
        return {
            "intercept": float(intercept),
            "coefficients": coefs.tolist(),
            "degree": self.degree,
        }
