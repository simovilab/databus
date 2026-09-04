"""Unit tests for RunLifecycleGuards.is_run_validated.

The VALIDATE_RUN -> INITIALIZE_RUN revalidation guard: re-runs the resource
availability checks and re-confirms the run's trip against whichever feed is
current *now*, closing the race window between validation and
initialization (including the nightly build_schedule feed rotation).

Real Postgres is used for the Feed/Trip/Run rows (guards.py already needs
Django DB access for these lookups); the module-level Redis client is
swapped for an in-memory fake since only `.get` is exercised by the guards
under test.
"""

from datetime import date

import pytest
from django.contrib.auth.models import User

from feed.models import Agency, Calendar, Feed, Route, Trip
from operations.models import Operator, Vehicle
from runs.domain.lifecycle import guards as guards_module
from runs.domain.lifecycle.events import RunLifecycleEvents
from runs.domain.lifecycle.guards import RunLifecycleGuards
from runs.domain.lifecycle.states import RunLifecycleStates
from runs.domain.lifecycle.transitions import Transition
from runs.models import Run
from runs.services.exceptions import RunLifecycleError


class _FakeRedis:
    """Stand-in for the module-level Redis client: only `.get` is used by the guards under test."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def get(self, key: str) -> bytes | None:
        """Return the stored value for `key` as bytes, or None if absent (mirrors redis-py's `.get`)."""
        value = self.store.get(key)
        return value.encode() if value is not None else None


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    """Swap the guards module's real Redis client for an in-memory fake."""
    fake = _FakeRedis()
    monkeypatch.setattr(guards_module, "r", fake)
    return fake


@pytest.fixture
def feed(db) -> Feed:
    """Create and return a Feed marked as the current GTFS feed."""
    return Feed.objects.create(feed_id="feed-1", is_current=True)


@pytest.fixture
def vehicle(db) -> Vehicle:
    """Create a Vehicle."""
    return Vehicle.objects.create(id="veh-1", license_plate="ABC-123")


@pytest.fixture
def operator(db) -> Operator:
    """Create an Operator backed by a fresh auth User."""
    user = User.objects.create_user(username="op-test", password="pw")
    return Operator.objects.create(id="op-1", user=user)


@pytest.fixture
def calendar(feed: Feed) -> Calendar:
    """Create a Calendar (service) valid all of 2026 in `feed`."""
    return Calendar.objects.create(
        feed=feed,
        service_id="svc-1",
        monday=True,
        tuesday=True,
        wednesday=True,
        thursday=True,
        friday=True,
        saturday=False,
        sunday=False,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )


@pytest.fixture
def route(feed: Feed) -> Route:
    """Create a Route in `feed`, with its required Agency."""
    agency = Agency.objects.create(
        feed=feed,
        agency_id="ag-1",
        agency_name="Test Agency",
        agency_url="https://example.com",
        agency_timezone="America/Costa_Rica",
    )
    return Route.objects.create(feed=feed, route_id="r-1", agency_id=agency.agency_id)


@pytest.fixture
def trip(feed: Feed, route: Route, calendar: Calendar) -> Trip:
    """Create a Trip in `feed` for `route`/`calendar`."""
    return Trip.objects.create(
        feed=feed,
        route_id=route.route_id,
        service_id=calendar.service_id,
        trip_id="t-1",
        direction_id=0,
        shape_id="s-1",
        wheelchair_accessible=0,
        bikes_allowed=0,
    )


@pytest.fixture
def run(vehicle: Vehicle, operator: Operator, trip: Trip) -> Run:
    """Create a VALIDATED Run for `trip`, claimed by `vehicle`/`operator`."""
    run = Run.objects.create(
        trip_id=trip.trip_id,
        route_id=trip.route_id,
        direction_id=trip.direction_id,
        shape_id=trip.shape_id,
        start_date=date.today(),
        run_lifecycle_state=RunLifecycleStates.VALIDATED,
    )
    run.vehicle.set([vehicle])
    run.operator.set([operator])
    return run


def _transition() -> Transition:
    return Transition(
        from_state=RunLifecycleStates.VALIDATED,
        event=RunLifecycleEvents.INITIALIZE_RUN,
        to_state=RunLifecycleStates.INITIALIZED,
        guards=[RunLifecycleGuards.is_run_validated],
        actions=[],
    )


def test_passes_when_resources_free(fake_redis: _FakeRedis, run: Run) -> None:
    """No Redis claims at all: every availability check and the trip lookup pass."""
    assert RunLifecycleGuards.is_run_validated(run, _transition(), {}) is True


def test_passes_when_claims_belong_to_this_run(
    fake_redis: _FakeRedis, run: Run, vehicle: Vehicle, operator: Operator, trip: Trip
) -> None:
    """A re-fire where this run already holds its own vehicle/trip/operator claims still passes."""
    fake_redis.store[f"vehicle:{vehicle.id}:current_run"] = str(run.id)
    fake_redis.store[f"trip:{trip.trip_id}:current_run"] = str(run.id)
    fake_redis.store[f"operator:{operator.id}:current_run"] = str(run.id)

    assert RunLifecycleGuards.is_run_validated(run, _transition(), {}) is True


def test_raises_when_vehicle_claimed_by_another_run(
    fake_redis: _FakeRedis, run: Run, vehicle: Vehicle
) -> None:
    """A vehicle claimed by a different run's ID raises with vehicle_id detail."""
    fake_redis.store[f"vehicle:{vehicle.id}:current_run"] = "some-other-run-id"

    with pytest.raises(RunLifecycleError) as exc_info:
        RunLifecycleGuards.is_run_validated(run, _transition(), {})
    assert "vehicle_id" in exc_info.value.errors


def test_raises_when_trip_claimed_by_another_run(
    fake_redis: _FakeRedis, run: Run, trip: Trip
) -> None:
    """A trip claimed by a different run's ID raises with trip_id detail."""
    fake_redis.store[f"trip:{trip.trip_id}:current_run"] = "some-other-run-id"

    with pytest.raises(RunLifecycleError) as exc_info:
        RunLifecycleGuards.is_run_validated(run, _transition(), {})
    assert "trip_id" in exc_info.value.errors


def test_raises_when_operator_claimed_by_another_run(
    fake_redis: _FakeRedis, run: Run, operator: Operator
) -> None:
    """An operator claimed by a different run's ID raises with operator_id detail."""
    fake_redis.store[f"operator:{operator.id}:current_run"] = "some-other-run-id"

    with pytest.raises(RunLifecycleError) as exc_info:
        RunLifecycleGuards.is_run_validated(run, _transition(), {})
    assert "operator_id" in exc_info.value.errors


def test_raises_when_trip_absent_from_current_feed(
    fake_redis: _FakeRedis, run: Run, trip: Trip, feed: Feed
) -> None:
    """If the feed rotated (nightly build_schedule) and the run's trip isn't in the new current feed, raise."""
    feed.is_current = False
    feed.save()
    Feed.objects.create(feed_id="feed-2", is_current=True)

    with pytest.raises(RunLifecycleError) as exc_info:
        RunLifecycleGuards.is_run_validated(run, _transition(), {})
    assert "trip_id" in exc_info.value.errors
