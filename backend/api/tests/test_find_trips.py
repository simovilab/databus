"""API tests for FindTripsView (`GET /api/find-trips/`).

Second step of the run-registration UI cascade: given a route/service/shape
selection, return candidate trips each tagged with the current lifecycle
state of any run for that trip today.
"""

from datetime import date, time

import pytest

from feed.models import Stop, Trip, TripTime
from runs.domain.lifecycle import RunLifecycleStates
from runs.models import Run


@pytest.fixture
def trip_time(trip: Trip, stop: Stop) -> TripTime:
    """Create a TripTime departure for `trip` at `stop`."""
    return TripTime.objects.create(
        feed=trip.feed,
        trip_id=trip.trip_id,
        stop_id=stop.stop_id,
        stop_sequence=1,
        departure_time=time(7, 0, 0),
    )


@pytest.mark.django_db
def test_returns_trip_tagged_unknown_when_no_run_exists(
    api_client, trip, trip_time, route
):
    """A matching trip with no Run today is tagged run_lifecycle_state=UNKNOWN."""
    response = api_client.get(
        "/api/find-trips/",
        {
            "route_id": trip.route_id,
            "service_id": trip.service_id,
            "shape_id": trip.shape_id,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "trip_id": trip.trip_id,
            "trip_time": "07:00:00",
            "run_lifecycle_state": "UNKNOWN",
            "direction_id": trip.direction_id,
            "trip_headsign": trip.trip_headsign,
        }
    ]


@pytest.mark.django_db
def test_returns_trip_tagged_with_its_run_lifecycle_state(
    api_client, trip, trip_time
):
    """A matching trip with a Run today is tagged with that run's actual lifecycle state."""
    Run.objects.create(
        trip_id=trip.trip_id,
        route_id=trip.route_id,
        direction_id=trip.direction_id,
        shape_id=trip.shape_id,
        start_date=date.today(),
        run_lifecycle_state=RunLifecycleStates.IN_PROGRESS,
    )

    response = api_client.get(
        "/api/find-trips/",
        {
            "route_id": trip.route_id,
            "service_id": trip.service_id,
            "shape_id": trip.shape_id,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["run_lifecycle_state"] == RunLifecycleStates.IN_PROGRESS.value


@pytest.mark.django_db
def test_missing_params_returns_400(api_client, current_feed):
    """Omitting any of route_id/service_id/shape_id returns a 400."""
    response = api_client.get("/api/find-trips/", {"route_id": "route-1"})

    assert response.status_code == 400
    assert "error" in response.json()
