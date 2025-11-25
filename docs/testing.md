# Testing Documentation

## Overview

This document describes the testing infrastructure for Databus, including unit tests, integration tests, contract tests, and CI/CD pipeline.

## Test Suite Structure

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── test_serializers.py         # Unit tests for serializers
├── test_api_endpoints.py       # Integration tests for API
├── test_gtfs_endpoints.py      # Integration tests for GTFS
└── test_contract.py            # Contract tests (OpenAPI validation)
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)

Tests individual components in isolation:
- Serializer validation
- Model methods
- Utility functions
- Business logic

**Run unit tests:**
```bash
pytest tests/ -m "unit" -v
```

### Integration Tests (`@pytest.mark.integration`)

Tests components working together:
- API endpoints with database
- Authentication flows
- Rate limiting with Redis
- Caching behavior
- GTFS data operations

**Run integration tests:**
```bash
pytest tests/ -m "integration" -v
```

### Contract Tests (`@pytest.mark.contract`)

Validates API responses against OpenAPI specification:
- Schema validation
- Response format verification
- Error response structure
- HTTP status codes
- Content-Type headers

**Run contract tests:**
```bash
pytest tests/ -m "contract" -v
```

## Running Tests

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test File
```bash
pytest tests/test_serializers.py -v
```

### Run Specific Test Class
```bash
pytest tests/test_api_endpoints.py::TestAPIClientEndpoints -v
```

### Run Specific Test Method
```bash
pytest tests/test_api_endpoints.py::TestAPIClientEndpoints::test_create_client -v
```

### Run with Coverage
```bash
pytest tests/ --cov=api --cov=feed --cov=gtfs --cov-report=html --cov-report=term-missing
```

### Run in Parallel (faster)
```bash
pytest tests/ -n auto
```

## Test Fixtures

Located in `tests/conftest.py`:

### Authentication Fixtures
- `user`: Regular user
- `staff_user`: Staff user
- `superuser`: Superuser/admin
- `jwt_token`: JWT access/refresh tokens
- `authenticated_client`: API client with JWT auth

### API Client Registry Fixtures
- `api_client_model`: APIClient instance
- `api_key`: APIKey with raw key value
- `client_quota`: ClientQuota with rate limits
- `client_usage_metrics`: Usage tracking metrics

### GTFS Fixtures
- `agency`: GTFS Agency
- `route`: GTFS Route
- `stop`: GTFS Stop with coordinates
- `trip`: GTFS Trip with calendar

### Infrastructure Fixtures
- `api_client`: DRF APIClient
- `django_client`: Django test client
- `redis_client`: Redis client for testing
- `mock_redis`: Mocked Redis (no real connection)

## Factory Boy

Use factories for creating test data:

```python
from tests.conftest import UserFactory, APIClientFactory

# Create single instance
user = UserFactory()

# Create multiple instances
users = UserFactory.create_batch(10)

# Override attributes
admin = UserFactory(is_staff=True, is_superuser=True)

# Build without saving to database
unsaved_user = UserFactory.build()
```

## Coverage Requirements

Target: **70% minimum coverage**

View coverage report:
```bash
pytest tests/ --cov=api --cov=feed --cov=gtfs --cov-report=html
open htmlcov/index.html
```

## CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on push/PR:

### Lint Job
- Black (code formatting)
- isort (import sorting)
- Flake8 (linting)
- Bandit (security scanning)

### Test Job
- PostgreSQL 18 + PostGIS
- Redis 8.4
- Unit tests
- Integration tests
- Contract tests
- Coverage report (uploaded to Codecov)

### Build Job
- Docker image build
- Docker image test

### Security Job
- Trivy vulnerability scanner
- SARIF report upload to GitHub Security

## Writing New Tests

### Unit Test Template

```python
import pytest
from api.serializers import MySerializer

@pytest.mark.unit
class TestMySerializer:
    """Tests for MySerializer."""
    
    def test_valid_data(self, db):
        """Test serializer with valid data."""
        data = {'field': 'value'}
        serializer = MySerializer(data=data)
        assert serializer.is_valid()
    
    def test_invalid_data(self, db):
        """Test serializer with invalid data."""
        data = {'field': 'invalid'}
        serializer = MySerializer(data=data)
        assert not serializer.is_valid()
        assert 'field' in serializer.errors
```

### Integration Test Template

```python
import pytest
from django.urls import reverse
from rest_framework import status

@pytest.mark.integration
@pytest.mark.database
class TestMyEndpoint:
    """Integration tests for my endpoint."""
    
    def test_get_endpoint(self, authenticated_client):
        """Test GET request."""
        url = reverse('api:my-endpoint')
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
    
    def test_post_endpoint(self, authenticated_client):
        """Test POST request."""
        url = reverse('api:my-endpoint')
        data = {'field': 'value'}
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
```

### Contract Test Template

```python
import pytest
from django.urls import reverse

@pytest.mark.contract
class TestMyContract:
    """Contract tests for my API."""
    
    def test_response_schema(self, authenticated_client):
        """Test response matches schema."""
        url = reverse('api:my-endpoint')
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.json()
        assert 'required_field' in data
        assert isinstance(data['required_field'], str)
```

## Best Practices

1. **Use descriptive test names**: `test_create_client_with_valid_data`
2. **One assertion per test** (when possible)
3. **Use fixtures** instead of setup/teardown methods
4. **Mock external services** (API calls, etc.)
5. **Test edge cases**: null values, empty strings, maximum lengths
6. **Test error conditions**: invalid input, missing fields
7. **Use markers** to categorize tests: `@pytest.mark.unit`, `@pytest.mark.slow`
8. **Document test purpose** with docstrings

## Troubleshooting

### Tests fail with database errors
```bash
# Reset test database
python manage.py migrate --noinput
pytest tests/ --create-db
```

### Tests fail with Redis errors
```bash
# Check Redis is running
redis-cli ping

# Use mock Redis
pytest tests/ -m "not redis"
```

### Coverage too low
```bash
# Find uncovered lines
pytest tests/ --cov=api --cov-report=term-missing

# Focus on specific module
pytest tests/ --cov=api.serializers --cov-report=term-missing
```

## Continuous Improvement

- Add tests for new features
- Maintain 70%+ coverage
- Update fixtures as models change
- Review and update contract tests when API changes
- Monitor CI/CD pipeline for failures

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-django](https://pytest-django.readthedocs.io/)
- [factory_boy](https://factoryboy.readthedocs.io/)
- [DRF Testing](https://www.django-rest-framework.org/api-guide/testing/)
- [Coverage.py](https://coverage.readthedocs.io/)
