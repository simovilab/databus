"""
ETA Service — low-latency inference with direct shape support.

Ported from eta_prediction/eta_service/estimator.py on branch
feature/eta_prediction with the following changes:
  - All sys.path hacks removed.
  - All imports rewritten to absolute gtfs_eta.* paths.
  - Module-level print() diagnostics removed (replaced with logging.debug).
  - os.environ mutation at import time removed.
  - Lazy imports inside _predict_with_model rewritten to gtfs_eta.* paths so
    all branches are consistent (only polyreg_distance is exercised by the
    baseline model, but the other branches compile cleanly).
  - ADDED: precomputed-distance hook — if an upcoming_stop dict carries a
    non-None 'shape_distance_to_stop' key, that value is used as the
    authoritative distance, bypassing both shape projection and haversine
    fallback for that stop (databus pre-computes a loop-back-safe monotonic
    distance and we prefer it).
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from gtfs_eta.feature_engineering.temporal import extract_temporal_features
from gtfs_eta.models.common.registry import get_registry

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional shape support
# ---------------------------------------------------------------------------
try:
    from gtfs_eta.feature_engineering.spatial import (
        ShapePolyline,
        calculate_distance_features_with_shape,
    )
    SHAPE_SUPPORT = True
except ImportError:
    SHAPE_SUPPORT = False
    _log.debug("Shape-aware spatial features not available; using fallback")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two lat/lon points in metres."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _progress_features_fallback(vehicle_position, stop, next_stop, total_segments_hint):
    """
    Approximate distance / progress metrics without shape data.
    Used when no ShapePolyline is available for the current trip.
    """
    vp_lat = vehicle_position["lat"]
    vp_lon = vehicle_position["lon"]
    stop_lat = stop["lat"]
    stop_lon = stop["lon"]

    distance_to_stop = haversine_distance(vp_lat, vp_lon, stop_lat, stop_lon)

    progress_on_segment = 0.0
    if next_stop:
        next_lat = next_stop["lat"]
        next_lon = next_stop["lon"]
        segment_length = haversine_distance(stop_lat, stop_lon, next_lat, next_lon)
        if segment_length > 0:
            distance_to_next = haversine_distance(vp_lat, vp_lon, next_lat, next_lon)
            progress_on_segment = max(0.0, min(1.0, 1.0 - (distance_to_next / segment_length)))

    stop_seq = (
        stop.get("stop_sequence")
        or stop.get("sequence")
        or stop.get("stop_order")
        or 1
    )
    total_segments = (
        stop.get("total_stop_sequence")
        or total_segments_hint
        or stop_seq
    )
    completed = max(float(stop_seq) - 1.0, 0.0)
    denom = max(float(total_segments), 1.0)
    progress_ratio = max(0.0, min(1.0, (completed + progress_on_segment) / denom))

    return {
        "distance_to_stop_m": distance_to_stop,
        "progress_on_segment": progress_on_segment,
        "progress_ratio": progress_ratio,
        "cross_track_error": None,
        "shape_progress": None,
        "shape_distance_to_stop": None,
    }


def _progress_features_with_shape(
    vehicle_position, stop, next_stop, shape, vehicle_stop_order, total_segments
):
    """
    Shape-aware distance / progress metrics using a pre-loaded ShapePolyline.
    Returns enhanced spatial features including cross-track error and
    shape-based distances.
    """
    features = calculate_distance_features_with_shape(
        vehicle_position=vehicle_position,
        stop=stop,
        next_stop=next_stop,
        shape=shape,
        vehicle_stop_order=vehicle_stop_order,
        total_segments=total_segments,
    )
    return {
        "distance_to_stop_m": features.get("distance_to_stop", 0.0),
        "progress_on_segment": features.get("progress_on_segment", 0.0),
        "progress_ratio": features.get("progress_ratio", 0.0),
        "cross_track_error": features.get("cross_track_error"),
        "shape_progress": features.get("shape_progress"),
        "shape_distance_to_stop": features.get("shape_distance_to_stop"),
    }


def _predict_with_model(model_key, model_type, features, distance_m):
    """
    Dispatch to the appropriate predict_eta function based on model_type.
    All lazy imports use absolute gtfs_eta.* paths.
    """
    if model_type == "historical_mean":
        from gtfs_eta.models.historical_mean.predict import predict_eta
        return predict_eta(
            model_key=model_key,
            route_id=features.get("route_id", "unknown"),
            stop_sequence=features.get("stop_sequence", 0),
            hour=features.get("hour", 0),
            day_of_week=features.get("day_of_week", 0),
            is_peak_hour=features.get("is_peak_hour", False),
        )

    elif model_type == "ewma":
        from gtfs_eta.models.ewma.predict import predict_eta
        return predict_eta(
            model_key=model_key,
            route_id=features.get("route_id", "unknown"),
            stop_sequence=features.get("stop_sequence", 0),
            hour=features.get("hour", 0),
        )

    elif model_type == "polyreg_distance":
        from gtfs_eta.models.polyreg_distance.predict import predict_eta
        return predict_eta(
            model_key=model_key,
            distance_to_stop=distance_m,
        )

    elif model_type == "polyreg_time":
        from gtfs_eta.models.polyreg_time.predict import predict_eta
        return predict_eta(
            model_key=model_key,
            distance_to_stop=distance_m,
            progress_on_segment=features.get("progress_on_segment"),
            progress_ratio=features.get("progress_ratio"),
            hour=features.get("hour", 0),
            day_of_week=features.get("day_of_week", 0),
            is_peak_hour=features.get("is_peak_hour", False),
            is_weekend=features.get("is_weekend", False),
            is_holiday=features.get("is_holiday", False),
            temperature_c=features.get("temperature_c", 25.0),
            precipitation_mm=features.get("precipitation_mm", 0.0),
            wind_speed_kmh=features.get("wind_speed_kmh"),
        )

    elif model_type == "xgboost":
        from gtfs_eta.models.xgb.predict import predict_eta
        return predict_eta(
            model_key=model_key,
            distance_to_stop=distance_m,
            progress_on_segment=features.get("progress_on_segment"),
            progress_ratio=features.get("progress_ratio"),
            hour=features.get("hour", 0),
            day_of_week=features.get("day_of_week", 0),
            is_peak_hour=features.get("is_peak_hour", False),
            is_weekend=features.get("is_weekend", False),
            is_holiday=features.get("is_holiday", False),
            temperature_c=features.get("temperature_c", 25.0),
            precipitation_mm=features.get("precipitation_mm", 0.0),
            wind_speed_kmh=features.get("wind_speed_kmh", None),
        )

    else:
        raise ValueError(f"Unknown model type: {model_type!r}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def estimate_stop_times(
    vehicle_position: dict,
    upcoming_stops: list[dict],
    route_id: str = None,
    trip_id: str = None,
    model_key: str = None,
    model_type: str = None,
    prefer_route_model: bool = True,
    max_stops: int = 3,
    shape: object = None,
) -> dict:
    """
    Estimate arrival times for upcoming stops based on vehicle position.

    LOW-LATENCY DESIGN: No database calls during inference.
    All data (stops, shapes) must be pre-loaded and passed as arguments.

    Args:
        vehicle_position: Dict with vehicle_id, route, lat, lon, speed, timestamp.
        upcoming_stops: List of stop dicts.  Each dict may include:
            - stop_id, stop_sequence, lat, lon  (always required)
            - shape_distance_to_stop (float, metres)  — OPTIONAL.
              When present and non-None, databus has pre-computed a
              loop-back-safe monotonic distance along the shape; that value
              is used directly as distance_m for the model, bypassing both
              ShapePolyline projection and haversine fallback for that stop.
        route_id: Optional route override.
        trip_id: Optional trip ID for metadata.
        model_key: Optional explicit model to use.
        model_type: Optional model type filter.
        prefer_route_model: If True, prefer route-specific models over global.
        max_stops: Maximum number of stops to predict.
        shape: Optional pre-loaded ShapePolyline object.

    Returns:
        Dict with predictions, model info, and metadata.
    """
    # Validate inputs
    if not vehicle_position or not upcoming_stops:
        return {
            "vehicle_id": vehicle_position.get("vehicle_id", "unknown") if vehicle_position else "unknown",
            "route_id": route_id,
            "trip_id": trip_id,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "model_key": None,
            "predictions": [],
            "error": "Missing vehicle position or stops",
        }

    stops_to_predict = upcoming_stops[:max_stops]

    # Parse timestamp
    vp_timestamp_str = vehicle_position["timestamp"]
    if vp_timestamp_str.endswith("Z"):
        vp_timestamp_str = vp_timestamp_str.replace("Z", "+00:00")
    vp_timestamp = datetime.fromisoformat(vp_timestamp_str)

    # Extract temporal features (Costa Rica locale by default)
    temporal_features = extract_temporal_features(
        vp_timestamp,
        tz="America/Costa_Rica",
        region="CR",
    )

    # Determine route
    if route_id is None:
        route_id = vehicle_position.get("route", "unknown")

    # Validate shape support
    shape_available = shape is not None and SHAPE_SUPPORT
    if shape and not SHAPE_SUPPORT:
        _log.debug("Shape provided but spatial module unavailable; using fallback")
        shape = None

    # Load registry and select model
    registry = get_registry()
    model_scope = "unknown"

    if model_key is None:
        if prefer_route_model and route_id and route_id != "unknown":
            model_key = registry.get_best_model(
                model_type=model_type,
                route_id=route_id,
                metric="test_mae_seconds",
            )
            model_scope = "route" if model_key else "global"
            if model_key is None:
                model_key = registry.get_best_model(
                    model_type=model_type,
                    route_id="global",
                    metric="test_mae_seconds",
                )
        else:
            model_key = registry.get_best_model(
                model_type=model_type,
                route_id="global",
                metric="test_mae_seconds",
            )
            model_scope = "global"

        # Last fallback — any model of the given type
        if model_key is None:
            model_key = registry.get_best_model(model_type=model_type)

        if model_key is None:
            return {
                "vehicle_id": vehicle_position["vehicle_id"],
                "route_id": route_id,
                "trip_id": trip_id,
                "computed_at": datetime.now(timezone.utc).isoformat(),
                "model_key": None,
                "predictions": [],
                "error": "No trained models found for model_type",
            }

    # Load model metadata
    try:
        model_metadata = registry.load_metadata(model_key)
        actual_model_type = model_metadata.get("model_type", "unknown")
        model_route_id = model_metadata.get("route_id")
        if model_route_id not in (None, "global"):
            model_scope = "route"
        elif model_scope == "unknown":
            model_scope = "global"
    except Exception as exc:
        return {
            "vehicle_id": vehicle_position["vehicle_id"],
            "route_id": route_id,
            "trip_id": trip_id,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "model_key": model_key,
            "predictions": [],
            "error": f"Failed to load model metadata: {exc}",
        }

    # -----------------------------------------------------------------------
    # Per-stop predictions
    # -----------------------------------------------------------------------
    predictions = []
    approx_total_segments = (
        max(
            (
                stop.get("total_stop_sequence")
                or stop.get("stop_sequence")
                or stop.get("sequence")
                or 0
            )
            for stop in stops_to_predict
        )
        if stops_to_predict
        else 0
    )
    if approx_total_segments <= 0:
        approx_total_segments = max(len(stops_to_predict), 1)

    for idx, stop in enumerate(stops_to_predict):
        next_stop = stops_to_predict[idx + 1] if idx + 1 < len(stops_to_predict) else None

        # Use explicit None checks, not `or`: stop_sequence == 0 is a valid
        # GTFS 0-based sequence and must not be treated as falsy (that would
        # relabel stop 0 as 1 and collide with a real stop 1).
        if stop.get("stop_sequence") is not None:
            stop_sequence_value = stop["stop_sequence"]
        elif stop.get("sequence") is not None:
            stop_sequence_value = stop["sequence"]
        elif stop.get("stop_order") is not None:
            stop_sequence_value = stop["stop_order"]
        else:
            stop_sequence_value = idx + 1

        # -------------------------------------------------------------------
        # PRECOMPUTED-DISTANCE HOOK
        # Databus pre-computes a loop-back-safe monotonic distance along the
        # shape for each upcoming stop and stores it as shape_distance_to_stop.
        # When present, we use it directly as the authoritative distance_m,
        # skipping both ShapePolyline projection and haversine fallback.
        # This avoids projection artifacts on looping routes and ensures the
        # distance is always non-decreasing across the stop list.
        # -------------------------------------------------------------------
        precomputed_dist = stop.get("shape_distance_to_stop")
        if precomputed_dist is not None:
            distance_m = float(precomputed_dist)
            spatial_features = {
                "distance_to_stop_m": distance_m,
                "progress_on_segment": 0.0,
                "progress_ratio": 0.0,
                "cross_track_error": None,
                "shape_progress": None,
                # Surface the precomputed distance so it appears in the
                # output prediction dict as shape_distance_to_stop_m.
                "shape_distance_to_stop": distance_m,
            }
        elif shape_available:
            spatial_features = _progress_features_with_shape(
                vehicle_position,
                stop,
                next_stop,
                shape,
                vehicle_stop_order=stop_sequence_value,
                total_segments=approx_total_segments,
            )
            distance_m = spatial_features["distance_to_stop_m"]
        else:
            spatial_features = _progress_features_fallback(
                vehicle_position,
                stop,
                next_stop,
                approx_total_segments,
            )
            distance_m = spatial_features["distance_to_stop_m"]

        # Build feature dict for the model
        progress_on_segment = spatial_features["progress_on_segment"] or 0.0
        progress_ratio = spatial_features["progress_ratio"] or 0.0

        features = {
            "route_id": route_id,
            "stop_sequence": stop_sequence_value,
            "distance_to_stop": distance_m,
            "progress_on_segment": progress_on_segment,
            "progress_ratio": progress_ratio,
            "hour": temporal_features["hour"],
            "day_of_week": temporal_features["day_of_week"],
            "is_weekend": temporal_features["is_weekend"],
            "is_holiday": temporal_features["is_holiday"],
            "is_peak_hour": temporal_features["is_peak_hour"],
            "temperature_c": 25.0,
            "precipitation_mm": 0.0,
            "wind_speed_kmh": None,
        }

        try:
            result = _predict_with_model(model_key, actual_model_type, features, distance_m)

            eta_seconds = result.get("eta_seconds", 0.0)
            eta_minutes = eta_seconds / 60.0
            eta_formatted = result.get(
                "eta_formatted",
                f"{int(eta_minutes)}m {int(eta_seconds % 60)}s",
            )
            eta_ts = datetime.fromtimestamp(
                vp_timestamp.timestamp() + eta_seconds, tz=timezone.utc
            )

            prediction = {
                "stop_id": stop["stop_id"],
                "stop_sequence": stop_sequence_value,
                "distance_to_stop_m": round(distance_m, 1),
                "eta_seconds": round(eta_seconds, 1),
                "eta_minutes": round(eta_minutes, 2),
                "eta_formatted": eta_formatted,
                "eta_timestamp": eta_ts.isoformat(),
            }

            # Optional shape metrics
            if spatial_features.get("cross_track_error") is not None:
                prediction["cross_track_error_m"] = round(spatial_features["cross_track_error"], 1)
            if spatial_features.get("shape_progress") is not None:
                prediction["shape_progress"] = round(spatial_features["shape_progress"], 3)
            if spatial_features.get("shape_distance_to_stop") is not None:
                prediction["shape_distance_to_stop_m"] = round(
                    spatial_features["shape_distance_to_stop"], 1
                )

            predictions.append(prediction)

        except Exception as exc:
            predictions.append(
                {
                    "stop_id": stop["stop_id"],
                    "stop_sequence": stop_sequence_value,
                    "distance_to_stop_m": round(distance_m, 1),
                    "eta_seconds": None,
                    "eta_minutes": None,
                    "eta_formatted": None,
                    "eta_timestamp": None,
                    "error": str(exc),
                }
            )

    return {
        "vehicle_id": vehicle_position["vehicle_id"],
        "route_id": route_id,
        "trip_id": trip_id,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "model_key": model_key,
        "model_type": actual_model_type,
        "model_scope": model_scope,
        "shape_used": shape_available,
        "predictions": predictions,
    }
