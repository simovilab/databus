# gtfs_eta

Inference-only ETA library: given a vehicle position and the upcoming stops on
its trip, predict arrival times from trained models stored in a model registry.

This is the **consumption half** of the ETA model lifecycle. It is consumed by
databus (`runs/domain/progression/stop_times.py`) to populate the
`run:<id>:stop_time_updates` projection that backs the GTFS-RT trip-updates feed.

## Provenance & intent

- **Vendored, not original.** The canonical source — including model training —
  lives in `gtfs-django` (`feature/eta_prediction`). This package is the slimmed
  inference half: estimator, feature engineering, and the model registry loader,
  with heavy training/serving deps dropped (`xgboost` is an optional extra).
- **Candidate for extraction.** It is namespaced (`gtfs_eta.*`) and databus
  depends on it through a single narrow seam (a lazy import in `stop_times.py`
  plus the workspace dependency). If a second consumer appears, or it needs an
  independent release cadence, it should move to its own package/repo — pulled
  the same way `gtfs-io` and `gtfs-django` are — and the move stays mechanical.
  Keep the databus → `gtfs_eta` seam narrow to preserve that.

## Model registry

Models are loaded from `MODEL_REGISTRY_DIR` (a `registry.json` index plus per-model
`*.pkl` / `*_meta.json`). Paths are resolved **relative to the registry directory**,
so the registry is relocatable: bind-mount it anywhere, check a placeholder into
version control, or have an external retraining suite write into it.

A deterministic placeholder global baseline can be (re)generated with:

```bash
MODEL_REGISTRY_DIR=eta_models python -m gtfs_eta.seed_baseline_model
```
