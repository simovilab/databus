"""Shared fixtures for api app tests: a minimal GTFS feed with one route, shape, and stop.

Built imperatively via the ORM (small, in-code fixture data) rather than the
large `feed/fixtures/gtfs.json` bundle, so each test only pulls in the rows
it actually needs.
"""

from datetime import date

import pytest
from django.contrib.gis.geos import LineString
from rest_framework.test import APIClient

from feed.models import Agency, Calendar, Feed, GeoShape, Route, RouteStop, Stop, Trip


@pytest.fixture
def api_client() -> APIClient:
    """Return an unauthenticated DRF test client."""
    return APIClient()


@pytest.fixture
def current_feed(db) -> Feed:
    """Create and return a Feed marked as the current GTFS feed."""
    return Feed.objects.create(feed_id="feed-1", is_current=True)


@pytest.fixture
def agency(current_feed: Feed) -> Agency:
    """Create an Agency in the current feed."""
    return Agency.objects.create(
        feed=current_feed,
        agency_id="agency-1",
        agency_name="Test Agency",
        agency_url="https://example.com",
        agency_timezone="America/Costa_Rica",
    )


@pytest.fixture
def route(current_feed: Feed, agency: Agency) -> Route:
    """Create a Route in the current feed, linked to `agency`."""
    return Route.objects.create(
        feed=current_feed,
        route_id="route-1",
        agency_id=agency.agency_id,
        route_short_name="1",
        route_long_name="Test Route",
    )


@pytest.fixture
def geo_shape(current_feed: Feed) -> GeoShape:
    """Create a GeoShape in the current feed with a two-point LineString."""
    return GeoShape.objects.create(
        feed=current_feed,
        shape_id="shape-1",
        geometry=LineString((-84.1, 9.9), (-84.0, 9.95)),
        shape_name="Test Shape",
        shape_desc="A shape for tests",
        shape_from="Origin",
        shape_to="Destination",
    )


@pytest.fixture
def stop(current_feed: Feed) -> Stop:
    """Create a Stop in the current feed."""
    return Stop.objects.create(
        feed=current_feed,
        stop_id="stop-1",
        stop_name="Test Stop",
        stop_lat=9.9,
        stop_lon=-84.1,
    )


@pytest.fixture
def route_stop(
    current_feed: Feed, route: Route, geo_shape: GeoShape, stop: Stop
) -> RouteStop:
    """Create a RouteStop tying `route` to `geo_shape` via `stop`."""
    return RouteStop.objects.create(
        feed=current_feed,
        route_id=route.route_id,
        shape_id=geo_shape.shape_id,
        direction_id=0,
        stop_id=stop.stop_id,
        stop_sequence=1,
        timepoint=True,
    )


@pytest.fixture
def calendar(current_feed: Feed) -> Calendar:
    """Create a Calendar (service) in the current feed, valid all of 2026."""
    return Calendar.objects.create(
        feed=current_feed,
        service_id="service-1",
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
def trip(current_feed: Feed, route: Route, calendar: Calendar, geo_shape: GeoShape) -> Trip:
    """Create a Trip in the current feed for `route`/`calendar`/`geo_shape`."""
    return Trip.objects.create(
        feed=current_feed,
        route_id=route.route_id,
        service_id=calendar.service_id,
        trip_id="trip-1",
        direction_id=0,
        shape_id=geo_shape.shape_id,
        trip_headsign="Test Headsign",
        wheelchair_accessible=0,
        bikes_allowed=0,
    )
