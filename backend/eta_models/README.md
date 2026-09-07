# ETA Models · committed baseline model registry

- **Purpose**: the committed, on-disk model registry consumed by the ETA estimator
  (`gtfs-eta`, the sibling `simovilab/gtfs-eta` repo, vendored via `uv` editable install — see
  `backend/pyproject.toml`). Ships one baseline model so a fresh checkout has a working estimator
  without training anything.
- **Contents**:
  - `registry.json` — the registry index: one entry per model key, with **relative** paths
  - `polyreg_distance_global_baseline_v0.pkl` — the fitted model artifact
  - `polyreg_distance_global_baseline_v0_meta.json` — its metadata (metrics, training params)

## Registry format

`registry.json` maps a model key to its metadata:

```json
{
  "polyreg_distance_global_baseline_v0": {
    "model_path": "polyreg_distance_global_baseline_v0.pkl",
    "meta_path": "polyreg_distance_global_baseline_v0_meta.json",
    "saved_at": "2026-08-19T00:41:44.406894",
    "model_type": "polyreg_distance",
    "route_id": null,
    "dataset": "synthetic_constant_speed"
  }
}
```

`model_path`/`meta_path` are stored **relative to the registry directory** — `gtfs-eta`'s
`ModelRegistry` joins them onto `base_dir` when loading, and falls back to matching by basename if
a stored path doesn't resolve directly, so the registry directory can be relocated wholesale
without editing `registry.json`. `route_id: null` marks a model as the **global** fallback (as
opposed to route-specific).

The shipped model is a synthetic baseline: `PolyRegDistanceModel(degree=1, alpha=1.0,
route_specific=False)` fit on 1000 synthetic constant-speed samples (~4.5 m/s, an urban bus
average) — not trained on real telemetry. It exists so `estimate_stop_times` always has *some*
model to fall back to.

## Seeding

This directory is seeded (and can be re-seeded) by the sibling `gtfs-eta` repo's script:

```
export MODEL_REGISTRY_DIR=backend/eta_models
python -m gtfs_eta.seed_baseline_model
```

(`gtfs-eta/gtfs_eta/seed_baseline_model.py`) — fits the model above and calls
`registry.save_model(MODEL_KEY, model, metadata, overwrite=True)`, which writes the `.pkl` +
`_meta.json` pair and updates `registry.json`.

## Consumer: the lazy-import seam

`runs/domain/progression/stop_times.py` is the only consumer in this codebase. It imports
`gtfs_eta.feature_engineering.spatial.ShapePolyline` and
`gtfs_eta.eta_service.estimator` **lazily**, inside `produce_stop_times`, specifically to keep
Django startup clean when the model registry / `gtfs-eta` extras aren't needed
(`runs/domain/progression/stop_times.py:182-193`). It's called by `realtime_engine/tasks.py` after
every successful position write, populating `run:<run_id>:stop_time_updates` in Redis for the
GTFS-RT builder.

## Configuration

- `MODEL_REGISTRY_DIR` — directory the registry loads from, read by `gtfs_eta`'s registry
  singleton itself (`os.getenv("MODEL_REGISTRY_DIR")`, falling back to `gtfs_eta`'s own config
  default) — not by Django settings. Point it at this directory (`backend/eta_models`) to use the
  committed baseline. Not currently set in `compose.dev.yml`; must be set explicitly wherever the
  worker that calls `produce_stop_times` runs.
- `ETA_MAX_STOPS` (default `3`) and `ETA_DEFAULT_UNCERTAINTY_S` (default `120`) — read directly by
  `runs/domain/progression/stop_times.py`, not by this directory, but they shape how the models
  here get used.

## Tests

No tests live in this directory (it is data, not code). The consumer seam is covered by
`runs/domain/progression/tests/test_stop_times_producer.py`, which points `MODEL_REGISTRY_DIR` at
a temp directory rather than this one.
