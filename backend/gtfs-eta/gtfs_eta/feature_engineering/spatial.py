"""
Shape-informed spatial feature extraction for gtfs_eta.

Ported from eta_prediction/feature_engineering/spatial.py on branch
feature/eta_prediction.  No sys.path hacks; no DB helper functions
(load_shape_from_gtfs / load_shape_for_trip) that require psycopg2 are
kept because they are not needed by the inference path.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple, Optional

EARTH_RADIUS_M = 6_371_000.0


def _deg2rad(x: float) -> float:
    return x * math.pi / 180.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    phi1, phi2 = _deg2rad(lat1), _deg2rad(lat2)
    dphi = phi2 - phi1
    dlambda = _deg2rad(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


class ShapePolyline:
    """
    Represents a route shape as an ordered sequence of (lat, lon) points.
    Provides methods to project vehicle positions onto the polyline and
    compute accurate progress along the route.
    """

    def __init__(self, points: List[Tuple[float, float]]):
        if len(points) < 2:
            raise ValueError("Shape must have at least 2 points")
        self.points = points
        self._segment_lengths = self._compute_segment_lengths()
        self._cumulative_distances = self._compute_cumulative_distances()
        self.total_length = self._cumulative_distances[-1]

    def _compute_segment_lengths(self) -> List[float]:
        lengths = []
        for i in range(len(self.points) - 1):
            lat1, lon1 = self.points[i]
            lat2, lon2 = self.points[i + 1]
            lengths.append(_haversine_m(lat1, lon1, lat2, lon2))
        return lengths

    def _compute_cumulative_distances(self) -> List[float]:
        cumulative = [0.0]
        for length in self._segment_lengths:
            cumulative.append(cumulative[-1] + length)
        return cumulative

    def project_point(self, lat: float, lon: float) -> Dict:
        """
        Project a point onto the polyline, finding the closest position.

        Returns:
            {
                'distance_along_shape': meters from shape start,
                'cross_track_distance': perpendicular distance from shape (meters),
                'closest_segment_idx': index of nearest segment,
                'progress': normalized progress [0, 1]
            }
        """
        min_dist = float("inf")
        best_segment_idx = 0
        best_projection_dist = 0.0

        for i in range(len(self.points) - 1):
            lat1, lon1 = self.points[i]
            lat2, lon2 = self.points[i + 1]
            proj_info = self._project_onto_segment(lat, lon, lat1, lon1, lat2, lon2)
            if proj_info["distance"] < min_dist:
                min_dist = proj_info["distance"]
                best_segment_idx = i
                best_projection_dist = proj_info["distance_along_segment"]

        distance_along_shape = (
            self._cumulative_distances[best_segment_idx] + best_projection_dist
        )
        progress = (
            distance_along_shape / self.total_length if self.total_length > 0 else 0.0
        )

        return {
            "distance_along_shape": distance_along_shape,
            "cross_track_distance": min_dist,
            "closest_segment_idx": best_segment_idx,
            "progress": min(1.0, max(0.0, progress)),
        }

    def _project_onto_segment(
        self,
        lat: float,
        lon: float,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> Dict:
        """Project point onto a single segment (planar approximation)."""
        avg_lat = (lat1 + lat2) / 2
        meters_per_deg_lat = 111320.0
        meters_per_deg_lon = 111320.0 * math.cos(_deg2rad(avg_lat))

        seg_x = (lon2 - lon1) * meters_per_deg_lon
        seg_y = (lat2 - lat1) * meters_per_deg_lat
        seg_length_sq = seg_x ** 2 + seg_y ** 2

        if seg_length_sq < 1e-6:
            dist = _haversine_m(lat, lon, lat1, lon1)
            return {"distance": dist, "distance_along_segment": 0.0}

        dx = (lon - lon1) * meters_per_deg_lon
        dy = (lat - lat1) * meters_per_deg_lat

        t = (dx * seg_x + dy * seg_y) / seg_length_sq
        t = max(0.0, min(1.0, t))

        proj_x = lon1 + t * (lon2 - lon1)
        proj_y = lat1 + t * (lat2 - lat1)

        dist = _haversine_m(lat, lon, proj_y, proj_x)
        seg_length = math.sqrt(seg_length_sq)
        distance_along_segment = t * seg_length

        return {"distance": dist, "distance_along_segment": distance_along_segment}

    def get_distance_between_stops(
        self,
        stop1_lat: float,
        stop1_lon: float,
        stop2_lat: float,
        stop2_lon: float,
    ) -> float:
        """Get shape distance between two stops (more accurate than haversine)."""
        proj1 = self.project_point(stop1_lat, stop1_lon)
        proj2 = self.project_point(stop2_lat, stop2_lon)
        return abs(proj2["distance_along_shape"] - proj1["distance_along_shape"])


def calculate_distance_features_with_shape(
    vehicle_position: Dict,
    stop: Dict,
    next_stop: Optional[Dict],
    shape: Optional[ShapePolyline] = None,
    vehicle_stop_order: Optional[int] = None,
    total_segments: Optional[int] = None,
) -> Dict:
    """
    Enhanced spatial feature extraction using shape data when available.

    Args:
        vehicle_position: {'lat': float, 'lon': float}
        stop: {'stop_id': str, 'lat': float, 'lon': float}
        next_stop: {'stop_id': str, 'lat': float, 'lon': float} or None
        shape: ShapePolyline instance or None
        vehicle_stop_order: 0-based index of the closest upstream stop
        total_segments: Total number of stop-to-stop segments in trip

    Returns:
        Dict with distance_to_stop, progress_on_segment, progress_ratio,
        shape_progress, shape_distance_to_stop, cross_track_error
    """
    vlat, vlon = float(vehicle_position["lat"]), float(vehicle_position["lon"])
    slat, slon = float(stop["lat"]), float(stop["lon"])

    result: Dict = {
        "distance_to_stop": _haversine_m(vlat, vlon, slat, slon),
        "distance_to_next_stop": None,
        "progress_on_segment": None,
        "progress_ratio": None,
        "shape_progress": None,
        "shape_distance_to_stop": None,
        "cross_track_error": None,
    }

    nlat = nlon = None
    if next_stop is not None:
        nlat, nlon = float(next_stop["lat"]), float(next_stop["lon"])
        seg_len = _haversine_m(slat, slon, nlat, nlon)
        result["distance_to_next_stop"] = (
            0.0 if seg_len == 0.0 else _haversine_m(vlat, vlon, nlat, nlon)
        )

    # Simple progress proxy when no shape
    if result["progress_on_segment"] is None and next_stop is not None and result["distance_to_next_stop"] is not None:
        seg_len = _haversine_m(slat, slon, nlat, nlon)
        if seg_len > 0:
            progress = 1.0 - (result["distance_to_next_stop"] / seg_len)
            result["progress_on_segment"] = max(0.0, min(1.0, progress))
        else:
            result["progress_on_segment"] = 0.0

    # Shape-based features
    if shape is not None:
        vehicle_proj = shape.project_point(vlat, vlon)
        stop_proj = shape.project_point(slat, slon)

        shape_dist_to_stop = (
            stop_proj["distance_along_shape"] - vehicle_proj["distance_along_shape"]
        )
        result.update(
            {
                "shape_progress": vehicle_proj["progress"],
                "shape_distance_to_stop": max(0, shape_dist_to_stop),
                "cross_track_error": vehicle_proj["cross_track_distance"],
                "progress_ratio": vehicle_proj["progress"],
            }
        )

        if next_stop is not None:
            next_proj = shape.project_point(nlat, nlon)
            segment_length = (
                next_proj["distance_along_shape"] - stop_proj["distance_along_shape"]
            )
            if segment_length > 0:
                past_stop = (
                    vehicle_proj["distance_along_shape"]
                    - stop_proj["distance_along_shape"]
                )
                result["progress_on_segment"] = max(
                    0.0, min(1.0, past_stop / segment_length)
                )
            else:
                result["progress_on_segment"] = 0.0

    # Fallback progress_ratio using stop order metadata
    if result["progress_ratio"] is None:
        order = vehicle_stop_order
        if order is None:
            order = stop.get("vehicle_stop_order") or stop.get("stop_order")
        segments = total_segments
        if segments is None:
            segments = stop.get("total_segments")
        if order is not None and segments:
            completed_segments = max(float(order), 0.0)
            progress_within = result["progress_on_segment"] or 0.0
            denom = max(float(segments), 1.0)
            ratio = (completed_segments + progress_within) / denom
            result["progress_ratio"] = max(0.0, min(1.0, ratio))

    return result
