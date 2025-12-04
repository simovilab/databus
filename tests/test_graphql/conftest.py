import pytest
from django.contrib.auth.models import User
from gtfs.models import Feed, Agency, Route, Stop, Trip, StopTime
from datetime import timedelta


@pytest.fixture
def create_user():
    """Factory fixture to create users"""

    def _create_user(username="testuser", is_staff=False, is_superuser=False):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="testpass123",
        )
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.save()
        return user

    return _create_user


@pytest.fixture
def auth_user(create_user):
    """Create a regular authenticated user"""
    return create_user("authuser", is_staff=False)


@pytest.fixture
def staff_user(create_user):
    """Create a staff user"""
    return create_user("staffuser", is_staff=True)


@pytest.fixture
def feed():
    """Create a test feed"""
    return Feed.objects.create(name="Test Feed", url="https://example.com/gtfs.zip")


@pytest.fixture
def agency(feed):
    """Create a test agency"""
    return Agency.objects.create(
        feed=feed,
        agency_id="TEST_AGENCY",
        agency_name="Test Transit Agency",
        agency_url="https://testtransit.com",
        agency_timezone="America/Los_Angeles",
        agency_lang="en",
        agency_phone="555-0100",
    )


@pytest.fixture
def route(feed, agency):
    """Create a test route"""
    return Route.objects.create(
        feed=feed,
        route_id="ROUTE_1",
        agency=agency,
        route_short_name="1",
        route_long_name="Downtown Express",
        route_type=3,  # Ciencias del Movimiento Humano
        route_color="FF0000",
        route_text_color="FFFFFF",
    )


@pytest.fixture
def stop(feed):
    """Create a test stop"""
    return Stop.objects.create(
        feed=feed,
        stop_id="STOP_1",
        stop_code="S1",
        stop_name="Main Street Station",
        stop_lat=37.7749,
        stop_lon=-122.4194,
        location_type=0,
    )


@pytest.fixture
def trip(feed, route):
    """Create a test trip"""
    return Trip.objects.create(
        feed=feed,
        route=route,
        service_id="WEEKDAY",
        trip_id="TRIP_1",
        trip_headsign="Downtown",
        direction_id=0,
        shape_id="SHAPE_1",
    )


@pytest.fixture
def stop_time(feed, trip, stop):
    """Create a test stop time"""
    return StopTime.objects.create(
        feed=feed,
        trip=trip,
        stop=stop,
        arrival_time=timedelta(hours=8, minutes=30),
        departure_time=timedelta(hours=8, minutes=31),
        stop_sequence=1,
        pickup_type=0,
        drop_off_type=0,
    )


@pytest.fixture
def multiple_agencies(feed):
    """Create multiple test agencies"""
    agencies = []
    for i in range(5):
        agency = Agency.objects.create(
            feed=feed,
            agency_id=f"AGENCY_{i}",
            agency_name=f"Transit Agency {i}",
            agency_url=f"https://transit{i}.com",
            agency_timezone="America/New_York",
        )
        agencies.append(agency)
    return agencies


@pytest.fixture
def multiple_routes(feed, agency):
    """Create multiple test routes"""
    routes = []
    for i in range(10):
        route = Route.objects.create(
            feed=feed,
            route_id=f"ROUTE_{i}",
            agency=agency,
            route_short_name=str(i),
            route_long_name=f"Route {i} Line",
            route_type=3,
        )
        routes.append(route)
    return routes
