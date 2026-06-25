"""
Model registry for gtfs_eta.

Manages trained model artifacts and metadata in a structured directory.
The registry dir is determined solely by the MODEL_REGISTRY_DIR environment
variable; no __file__-relative paths are used so the package is relocatable.

Ported from eta_prediction/models/common/registry.py on branch
feature/eta_prediction with the following changes:
  - Removed sys.path hacks (not needed in a proper package).
  - Removed print() diagnostics; replaced with logging.
  - PROJECT_ROOT / DEFAULT_REGISTRY_DIR no longer derived from __file__ —
    the env var is the only authoritative source.
  - _find_existing_registry_dir() retained as a convenience fallback for
    local dev (walks CWD upwards looking for models/trained/registry.json).
  - get_registry() singleton caching retained.
"""

import json
import logging
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

_log = logging.getLogger(__name__)

# ── Directory resolution ──────────────────────────────────────────────────────

def _find_existing_registry_dir() -> Optional[Path]:
    """
    Walk CWD upward searching for an existing models/trained/registry.json.
    Returns None if not found (caller should then raise or use a default).
    """
    cwd = Path.cwd().resolve()
    for root in [cwd, *cwd.parents]:
        candidate = root / "models" / "trained"
        if (candidate / "registry.json").exists():
            return candidate.resolve()
    return None


def _resolve_registry_dir() -> Path:
    """
    Determine the registry directory with this priority:
      1. MODEL_REGISTRY_DIR env var (authoritative).
      2. Walk CWD upward for an existing registry (dev convenience).
      3. Raise at runtime if neither is available.
    """
    env_dir = os.getenv("MODEL_REGISTRY_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    discovered = _find_existing_registry_dir()
    if discovered:
        return discovered
    raise RuntimeError(
        "MODEL_REGISTRY_DIR is not set and no existing registry was found. "
        "Set the MODEL_REGISTRY_DIR environment variable before using gtfs_eta."
    )


# ── Registry class ────────────────────────────────────────────────────────────

class ModelRegistry:
    """
    Manages model artifacts and metadata in a structured directory.

    Structure::

        <registry_dir>/
          {model_key}.pkl
          {model_key}_meta.json
          registry.json          # index of all models
    """

    def __init__(self, base_dir: Union[str, Path, None] = None):
        if base_dir is not None:
            base_path = Path(base_dir).expanduser().resolve()
        else:
            base_path = _resolve_registry_dir()

        self.base_dir = base_path
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.registry_file = self.base_dir / "registry.json"
        self._load_registry()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load_registry(self) -> None:
        if self.registry_file.exists():
            with open(self.registry_file, "r") as f:
                self.registry: Dict[str, Any] = json.load(f)
        else:
            self.registry = {}

    def _save_registry(self) -> None:
        with open(self.registry_file, "w") as f:
            json.dump(self.registry, f, indent=2)

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def save_model(
        self,
        model_key: str,
        model: Any,
        metadata: Dict[str, Any],
        overwrite: bool = False,
    ) -> Path:
        """Save model pickle + metadata JSON; update the registry index."""
        model_path = self.base_dir / f"{model_key}.pkl"
        meta_path = self.base_dir / f"{model_key}_meta.json"

        if model_path.exists() and not overwrite:
            raise FileExistsError(
                f"Model {model_key} already exists. Set overwrite=True to replace."
            )

        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        metadata = dict(metadata)  # don't mutate caller's dict
        metadata["model_key"] = model_key
        metadata["saved_at"] = datetime.now().isoformat()
        metadata["model_path"] = model_path.name

        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        route_info = (
            f" (route: {metadata.get('route_id')})"
            if metadata.get("route_id")
            else " (global)"
        )
        _log.debug("Saved model: %s%s", model_key, route_info)

        # Store basenames only — paths are resolved against ``base_dir`` at
        # load time (see ``_resolve_in_registry``), keeping the registry
        # relocatable: a registry directory can be moved, bind-mounted at a
        # different root, or checked into version control and still load.
        self.registry[model_key] = {
            "model_path": model_path.name,
            "meta_path": meta_path.name,
            "saved_at": metadata["saved_at"],
            "model_type": metadata.get("model_type", "unknown"),
            "route_id": metadata.get("route_id"),
            "dataset": metadata.get("dataset", "unknown"),
        }
        self._save_registry()
        return model_path

    def _resolve_in_registry(self, stored_path: str) -> Path:
        """Resolve a registry-stored path against the registry directory.

        Only the basename of ``stored_path`` is used, so entries written with
        an absolute path on another host (e.g. ``/app/eta_models/x.pkl``) still
        load wherever the registry directory currently lives.
        """
        return self.base_dir / Path(stored_path).name

    def load_model(self, model_key: str) -> Any:
        """Load and unpickle a model from the registry."""
        if model_key not in self.registry:
            raise KeyError(f"Model {model_key!r} not found in registry")
        model_path = self._resolve_in_registry(self.registry[model_key]["model_path"])
        with open(model_path, "rb") as f:
            return pickle.load(f)

    def load_metadata(self, model_key: str) -> Dict[str, Any]:
        """Load metadata JSON for a model."""
        if model_key not in self.registry:
            raise KeyError(f"Model {model_key!r} not found in registry")
        meta_path = self._resolve_in_registry(self.registry[model_key]["meta_path"])
        with open(meta_path, "r") as f:
            return json.load(f)

    def delete_model(self, model_key: str) -> bool:
        """Remove model pickle, metadata, and registry entry."""
        if model_key not in self.registry:
            raise KeyError(f"Model {model_key!r} not found in registry")

        model_path = self._resolve_in_registry(self.registry[model_key]["model_path"])
        meta_path = self._resolve_in_registry(self.registry[model_key]["meta_path"])

        if model_path.exists():
            model_path.unlink()
        if meta_path.exists():
            meta_path.unlink()

        del self.registry[model_key]
        self._save_registry()
        _log.debug("Deleted model: %s", model_key)
        return True

    # ── query helpers ─────────────────────────────────────────────────────────

    def list_models(
        self,
        model_type: Optional[str] = None,
        route_id: Optional[str] = None,
        sort_by: str = "saved_at",
    ) -> pd.DataFrame:
        """Return a DataFrame of all models matching the given filters."""
        models = []
        for key, info in self.registry.items():
            if model_type and info.get("model_type") != model_type:
                continue
            model_route_id = info.get("route_id")
            if route_id is not None and route_id != "all":
                if route_id == "global" and model_route_id is not None:
                    continue
                elif route_id != "global" and model_route_id != route_id:
                    continue
            try:
                meta = self.load_metadata(key)
                models.append(
                    {
                        "model_key": key,
                        "model_type": info.get("model_type", "unknown"),
                        "route_id": model_route_id or "global",
                        "saved_at": info["saved_at"],
                        "dataset": meta.get("dataset", "unknown"),
                        "n_samples": meta.get("n_samples"),
                        "mae_seconds": meta.get("metrics", {}).get("test_mae_seconds"),
                        "mae_minutes": meta.get("metrics", {}).get("test_mae_minutes"),
                        "rmse_seconds": meta.get("metrics", {}).get("test_rmse_seconds"),
                        "r2": meta.get("metrics", {}).get("test_r2"),
                    }
                )
            except Exception as exc:
                _log.warning("Could not load metadata for %s: %s", key, exc)

        df = pd.DataFrame(models)
        if not df.empty and sort_by in df.columns:
            df = df.sort_values(sort_by, ascending=False)
        return df

    def get_best_model(
        self,
        model_type: Optional[str] = None,
        route_id: Optional[str] = None,
        metric: str = "test_mae_seconds",
        minimize: bool = True,
    ) -> Optional[str]:
        """
        Return the model_key of the best model by the given metric.

        When route_id is None, prefers route-specific models if they exist;
        otherwise falls back to global models.
        """
        candidates = []
        for key in self.registry:
            if model_type and self.registry[key].get("model_type") != model_type:
                continue

            model_route_id = self.registry[key].get("route_id")
            if route_id is not None:
                if route_id == "global" and model_route_id is not None:
                    continue
                elif route_id != "global" and model_route_id != route_id:
                    continue

            try:
                meta = self.load_metadata(key)
                metric_value = meta.get("metrics", {}).get(metric)
                if metric_value is not None:
                    candidates.append(
                        {
                            "key": key,
                            "metric_value": metric_value,
                            "route_id": model_route_id,
                            "is_route_specific": model_route_id is not None,
                        }
                    )
            except Exception:
                continue

        if not candidates:
            return None

        if route_id is None:
            route_specific = [c for c in candidates if c["is_route_specific"]]
            global_models = [c for c in candidates if not c["is_route_specific"]]
            candidates_to_sort = route_specific if route_specific else global_models
        else:
            candidates_to_sort = candidates

        candidates_to_sort.sort(key=lambda x: x["metric_value"], reverse=not minimize)
        return candidates_to_sort[0]["key"] if candidates_to_sort else None

    def get_routes(self, model_type: Optional[str] = None) -> List[str]:
        """Return sorted list of route IDs that have trained models."""
        routes = set()
        for key, info in self.registry.items():
            if model_type and info.get("model_type") != model_type:
                continue
            route = info.get("route_id")
            if route is not None:
                routes.add(route)
        return sorted(routes)


# ── Singleton ─────────────────────────────────────────────────────────────────

_registry: Optional[ModelRegistry] = None


def get_registry() -> ModelRegistry:
    """Return (or lazily create) the process-level registry singleton."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
