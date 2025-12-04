#!/usr/bin/env python
"""
Validation script for GraphQL API implementation.
Checks that all modules can be imported and schema can be built.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment variables for testing
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("ALLOWED_HOSTS", "localhost")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "realtime.settings")

print("=" * 60)
print("GraphQL API Implementation Validation")
print("=" * 60)

# Test 1: Import Django and setup
print("\n1. Testing Django setup...")
try:
    import django

    django.setup()
    print("   ✓ Django setup successful")
except Exception as e:
    print(f"   ✗ Django setup failed: {e}")
    sys.exit(1)

# Test 2: Import models
print("\n2. Testing GTFS models...")
try:
    from gtfs.models import (
        Agency,
        Feed,
        Route,
        Stop,
        Trip,
        StopTime,
        Calendar,
        CalendarDate,
    )

    print("   ✓ GTFS models imported successfully")
except Exception as e:
    print(f"   ✗ GTFS models import failed: {e}")
    sys.exit(1)

# Test 3: Import GraphQL types
print("\n3. Testing GraphQL types...")
try:
    from graphql_api.types import (
        AgencyType,
        RouteType,
        StopType,
        TripType,
        StopTimeType,
        FeedType,
        PageInfo,
        AgencyConnection,
        CreateAgencyInput,
        CreateAgencyPayload,
    )

    print("   ✓ GraphQL types imported successfully")
except Exception as e:
    print(f"   ✗ GraphQL types import failed: {e}")
    sys.exit(1)

# Test 4: Import permissions
print("\n4. Testing permissions...")
try:
    from graphql_api.permissions import IsAuthenticated, IsStaff

    print("   ✓ Permissions imported successfully")
except Exception as e:
    print(f"   ✗ Permissions import failed: {e}")
    sys.exit(1)

# Test 5: Import queries
print("\n5. Testing queries...")
try:
    from graphql_api.queries import Query

    print("   ✓ Queries imported successfully")
except Exception as e:
    print(f"   ✗ Queries import failed: {e}")
    sys.exit(1)

# Test 6: Import mutations
print("\n6. Testing mutations...")
try:
    from graphql_api.mutations import Mutation

    print("   ✓ Mutations imported successfully")
except Exception as e:
    print(f"   ✗ Mutations import failed: {e}")
    sys.exit(1)

# Test 7: Build schema
print("\n7. Testing schema construction...")
try:
    from graphql_api.schema import schema

    print("   ✓ Schema built successfully")
except Exception as e:
    print(f"   ✗ Schema build failed: {e}")
    sys.exit(1)

# Test 8: Verify schema structure
print("\n8. Testing schema structure...")
try:
    # Check that schema has graphql_schema attribute
    assert hasattr(schema, "graphql_schema"), "Schema doesn't have graphql_schema"
    graphql_schema = schema.graphql_schema
    
    # Check query type
    query_type = graphql_schema.query_type
    assert query_type is not None, "Query type is None"
    assert query_type.name == "Query", f"Query type name is {query_type.name}"
    print("   ✓ Query type is valid")

    # Check mutation type
    mutation_type = graphql_schema.mutation_type
    assert mutation_type is not None, "Mutation type is None"
    assert (
        mutation_type.name == "Mutation"
    ), f"Mutation type name is {mutation_type.name}"
    print("   ✓ Mutation type is valid")

    # Check query fields
    query_fields = list(query_type.fields.keys())
    expected_queries = [
        "allFeeds",
        "feed",
        "allAgencies",
        "agency",
        "allRoutes",
        "route",
        "allStops",
        "stop",
        "tripsByRoute",
        "trip",
        "stopTimesByTrip",
        "stopTime",
    ]

    for expected in expected_queries:
        assert expected in query_fields, f"Query {expected} not found"
    print(f"   ✓ All {len(expected_queries)} expected queries present")

    # Check mutation fields
    mutation_fields = list(mutation_type.fields.keys())
    expected_mutations = ["createAgency"]

    for expected in expected_mutations:
        assert expected in mutation_fields, f"Mutation {expected} not found"
    print(f"   ✓ All {len(expected_mutations)} expected mutations present")

except Exception as e:
    print(f"   ✗ Schema structure validation failed: {e}")
    sys.exit(1)

# Test 9: Import URL configuration
print("\n9. Testing URL configuration...")
try:
    from graphql_api.urls import urlpatterns

    assert len(urlpatterns) > 0, "No URL patterns defined"
    print("   ✓ URL configuration valid")
except Exception as e:
    print(f"   ✗ URL configuration failed: {e}")
    sys.exit(1)

# Test 10: Check app configuration
print("\n10. Testing app configuration...")
try:
    from django.apps import apps

    graphql_app = apps.get_app_config("graphql_api")
    assert graphql_app is not None, "GraphQL app not registered"
    print("   ✓ GraphQL app registered successfully")

    gtfs_app = apps.get_app_config("gtfs")
    assert gtfs_app is not None, "GTFS app not registered"
    print("   ✓ GTFS app registered successfully")
except Exception as e:
    print(f"   ✗ App configuration failed: {e}")
    sys.exit(1)

# Summary
print("\n" + "=" * 60)
print("✓ All validation checks passed!")
print("=" * 60)
print("\nNext steps:")
print("1. Run migrations: python manage.py makemigrations && python manage.py migrate")
print("2. Create a superuser: python manage.py createsuperuser")
print("3. Run the server: python manage.py runserver")
print("4. Access GraphQL at: http://localhost:8000/graphql/")
print("5. Run tests: pytest tests/test_graphql/")
print()
