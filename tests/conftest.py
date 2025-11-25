"""
Pytest fixtures and configuration for Databus tests.

Provides shared fixtures for testing API clients, authentication,
rate limiting, caching, and more.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from faker import Faker
import factory
from datetime import timedelta
from django.utils import timezone

# Initialize Faker
fake = Faker()


@pytest.fixture
def api_client():
    """Provides DRF API client."""
    return APIClient()


@pytest.fixture
def django_client():
    """Provides Django test client."""
    return Client()


@pytest.fixture
def user(db):
    """Creates a regular user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def staff_user(db):
    """Creates a staff user."""
    return User.objects.create_user(
        username='staffuser',
        email='staff@example.com',
        password='staffpass123',
        is_staff=True
    )


@pytest.fixture
def superuser(db):
    """Creates a superuser."""
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123'
    )


@pytest.fixture
def jwt_token(user):
    """Generates JWT token for user."""
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh)
    }


@pytest.fixture
def authenticated_client(api_client, jwt_token):
    """Provides authenticated API client with JWT."""
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {jwt_token["access"]}')
    return api_client


@pytest.fixture
def staff_authenticated_client(api_client, staff_user):
    """Provides authenticated staff client."""
    refresh = RefreshToken.for_user(staff_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


# API Client Registry Fixtures

@pytest.fixture
def api_client_model(db):
    """Creates an API client."""
    from api.models import APIClient
    return APIClient.objects.create(
        client_name='Test Client',
        client_type='vehicle',
        contact_email='client@example.com',
        status='active'
    )


@pytest.fixture
def api_key(api_client_model):
    """Creates an API key for client."""
    from api.models import APIKey
    key, key_value = APIKey.generate_key()
    api_key = APIKey.objects.create(
        client=api_client_model,
        name='Test Key',
        key=key,
        expires_at=timezone.now() + timedelta(days=30)
    )
    # Store the raw key value for testing
    api_key.raw_key = key_value
    return api_key


@pytest.fixture
def client_quota(api_client_model):
    """Creates quota for client."""
    from api.models import ClientQuota
    return ClientQuota.objects.create(
        client=api_client_model,
        requests_per_minute=60,
        requests_per_hour=1000,
        requests_per_day=10000,
        can_write=True,
        can_subscribe_realtime=True
    )


@pytest.fixture
def client_usage_metrics(api_client_model):
    """Creates usage metrics for client."""
    from api.models import ClientUsageMetrics
    return ClientUsageMetrics.objects.create(
        client=api_client_model,
        request_count=100,
        error_count=2,
        avg_response_time=150.0,
        p95_response_time=200.0,
        p99_response_time=300.0
    )


# GTFS Fixtures

@pytest.fixture
def agency(db):
    """Creates a GTFS agency."""
    from gtfs.models import Agency
    return Agency.objects.create(
        agency_id='test-agency',
        agency_name='Test Transit',
        agency_url='https://test-transit.example.com',
        agency_timezone='America/Costa_Rica'
    )


@pytest.fixture
def route(agency):
    """Creates a GTFS route."""
    from gtfs.models import Route
    return Route.objects.create(
        route_id='test-route-1',
        agency=agency,
        route_short_name='1',
        route_long_name='Test Route 1',
        route_type=3  # Bus
    )


@pytest.fixture
def stop(db):
    """Creates a GTFS stop."""
    from gtfs.models import Stop
    return Stop.objects.create(
        stop_id='test-stop-1',
        stop_name='Test Stop 1',
        stop_lat=9.9281,
        stop_lon=-84.0907
    )


@pytest.fixture
def trip(route):
    """Creates a GTFS trip."""
    from gtfs.models import Trip, Calendar
    
    # Create calendar first
    calendar = Calendar.objects.create(
        service_id='weekday',
        monday=True,
        tuesday=True,
        wednesday=True,
        thursday=True,
        friday=True,
        saturday=False,
        sunday=False,
        start_date='2025-01-01',
        end_date='2025-12-31'
    )
    
    return Trip.objects.create(
        trip_id='test-trip-1',
        route=route,
        service=calendar,
        direction_id=0
    )


# Redis Fixtures

@pytest.fixture
def redis_client():
    """Provides Redis client for testing."""
    import redis
    from django.conf import settings
    
    client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB + 1,  # Use different DB for tests
        decode_responses=True
    )
    
    # Clear test database before tests
    client.flushdb()
    
    yield client
    
    # Cleanup after tests
    client.flushdb()
    client.close()


# Factory Boy Factories

class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating User instances."""
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True


class APIClientFactory(factory.django.DjangoModelFactory):
    """Factory for creating APIClient instances."""
    class Meta:
        model = 'api.APIClient'
    
    client_name = factory.Faker('company')
    client_type = 'vehicle'
    contact_email = factory.Faker('email')
    status = 'active'
    organization = factory.Faker('company')


class AgencyFactory(factory.django.DjangoModelFactory):
    """Factory for creating GTFS Agency instances."""
    class Meta:
        model = 'gtfs.Agency'
    
    agency_id = factory.Sequence(lambda n: f'agency-{n}')
    agency_name = factory.Faker('company')
    agency_url = factory.Faker('url')
    agency_timezone = 'America/Costa_Rica'


# Pytest hooks and configuration

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "contract: mark test as a contract test"
    )


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Enable database access for all tests by default."""
    pass


@pytest.fixture
def mock_redis(mocker):
    """Mock Redis for tests that don't need real Redis."""
    mock = mocker.Mock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.incr.return_value = 1
    mock.expire.return_value = True
    return mock
