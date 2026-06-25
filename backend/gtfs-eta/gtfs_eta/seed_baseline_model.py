"""
seed_baseline_model.py — seed ONE global polyreg_distance model into the registry.

Usage:
    export MODEL_REGISTRY_DIR=/tmp/gtfs_eta_registry
    python gtfs_eta/seed_baseline_model.py

The script:
  1. Builds synthetic constant-speed data (distance / 4.5 m/s ≈ urban bus avg).
  2. Fits a PolyRegDistanceModel(degree=1, alpha=1.0, route_specific=False).
  3. Saves it to the registry with the key 'polyreg_distance_global_baseline_v0'.

MODEL_REGISTRY_DIR is read by the registry singleton; set it before running.
"""

import os
import sys

import numpy as np
import pandas as pd

# Allow running as a top-level script from the repo root
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from gtfs_eta.models.polyreg_distance.model import PolyRegDistanceModel
from gtfs_eta.models.common.registry import get_registry

# ── Constants ─────────────────────────────────────────────────────────────────

MODEL_KEY = "polyreg_distance_global_baseline_v0"
SPEED_M_S = 4.5          # urban bus average including dwell time
N_SAMPLES = 1_000
DISTANCE_MAX_M = 3_000
NOISE_STD_S = 10.0       # small gaussian noise on arrival time
RANDOM_SEED = 42


def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED)

    # Synthetic training data
    distances = rng.uniform(0, DISTANCE_MAX_M, size=N_SAMPLES)
    times = distances / SPEED_M_S + rng.normal(0, NOISE_STD_S, size=N_SAMPLES)
    times = np.clip(times, 0, None)  # no negative travel times

    train_df = pd.DataFrame(
        {
            "distance_to_stop": distances,
            "time_to_arrival_seconds": times,
        }
    )

    # Build and fit model
    model = PolyRegDistanceModel(degree=1, alpha=1.0, route_specific=False)
    model.fit(train_df)

    # Verify that the global model path is available (used by predict())
    assert model.global_model is not None, "global_model should be set after fit()"

    # Quick sanity check: ETA at 1000 m should be ~222 s
    _check_df = pd.DataFrame({"distance_to_stop": [1000.0]})
    eta_check = float(model.predict(_check_df)[0])
    expected = 1000.0 / SPEED_M_S
    assert abs(eta_check - expected) < 60, (
        f"Sanity check failed: predicted {eta_check:.1f}s, expected ~{expected:.1f}s"
    )

    # Metadata (get_best_model requires metrics.test_mae_seconds to be
    # present and non-None)
    metadata = {
        "model_type": "polyreg_distance",
        "route_id": None,           # None → registered as GLOBAL
        "route_specific": False,
        "degree": 1,
        "alpha": 1.0,
        "dataset": "synthetic_constant_speed",
        "n_samples": N_SAMPLES,
        "metrics": {
            "test_mae_seconds": 30.0,
            "test_mae_minutes": 0.5,
        },
    }

    registry = get_registry()
    model_path = registry.save_model(MODEL_KEY, model, metadata, overwrite=True)
    print(f"Seeded model '{MODEL_KEY}' -> {model_path}")
    print(f"Registry dir: {registry.base_dir}")


if __name__ == "__main__":
    main()
