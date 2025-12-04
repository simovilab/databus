#!/usr/bin/env python
"""
Script de validación para la implementación de la API GraphQL.
Verifica que todos los módulos puedan ser importados y que el esquema pueda ser construido.
"""

import sys
import os


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar variables de entorno para pruebas
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
print(" Validando API GraphQL")
print("=" * 60)

# Test 1: Importar Django y configuración
print("\n1. Testeando el Django setup...")
try:
    import django

    django.setup()
    print("   ✓ Django setup exitoso")
except Exception as e:
    print(f"   ✗ Django setup fallido: {e}")
    sys.exit(1)

# Test 2: Importar modelos
print("\n2. Testeando los modelos GTFS...")
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

    print("   ✓ Modelos GTFS importados exitosamente")
except Exception as e:
    print(f"   ✗ Fallo al importar los modelos GTFS: {e}")
    sys.exit(1)

# Test 3: Importar tipos GraphQL
print("\n3. Testeando los tipos GraphQL...")
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

    print("   ✓ Tipos GraphQL importados exitosamente")
except Exception as e:
    print(f"   ✗ Fallo al importar los tipos GraphQL: {e}")
    sys.exit(1)

# Test 4: Importar permisos
print("\n4. Testeando los permisos...")
try:
    from graphql_api.permissions import IsAuthenticated, IsStaff

    print("   ✓ Permisos importados exitosamente")
except Exception as e:
    print(f"   ✗ Fallo al importar los permisos: {e}")
    sys.exit(1)

# Test 5: Importar consultas
print("\n5. Testeando las consultas...")
try:
    from graphql_api.queries import Query

    print("   ✓ Consultas importadas exitosamente")
except Exception as e:
    print(f"   ✗ Fallo al importar las consultas: {e}")
    sys.exit(1)

# Test 6: Importar mutaciones
print("\n6. Testeando las mutaciones...")
try:
    from graphql_api.mutations import Mutation

    print("   ✓ Mutaciones importadas exitosamente")
except Exception as e:
    print(f"   ✗ Fallo al importar las mutaciones: {e}")
    sys.exit(1)

# Test 7: Construcción del esquema
print("\n7. Testeando la construcción del esquema...")
try:
    from graphql_api.schema import schema

    print("   ✓ Esquema construido exitosamente")
except Exception as e:
    print(f"   ✗ Fallo en la construcción del esquema: {e}")
    sys.exit(1)

# Test 8: Verify schema structure
print("\n8. Testeando la estructura del esquema...")
try:
    # Check that schema has graphql_schema attribute
    assert hasattr(schema, "graphql_schema"), "El esquema no tiene graphql_schema"
    graphql_schema = schema.graphql_schema
    
    # Check query type
    query_type = graphql_schema.query_type
    assert query_type is not None, "El tipo de consulta es None"
    assert query_type.name == "Query", f"El nombre del tipo de consulta es {query_type.name}"
    print("   ✓ El tipo de consulta es válido")

    # Check mutation type
    mutation_type = graphql_schema.mutation_type
    assert mutation_type is not None, "El tipo de mutación es None"
    assert (
        mutation_type.name == "Mutation"
    ), f"El nombre del tipo de mutación es {mutation_type.name}"
    print("   ✓ El tipo de mutación es válido")
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
        assert expected in query_fields, f"Query {expected} no encontrado"
    print(f"   ✓ Todas las {len(expected_queries)} consultas esperadas están presentes")

    # Check mutation fields
    mutation_fields = list(mutation_type.fields.keys())
    expected_mutations = ["createAgency"]

    for expected in expected_mutations:
        assert expected in mutation_fields, f"Mutación {expected} no encontrada"
    print(f"   ✓ Todas las {len(expected_mutations)} mutaciones esperadas están presentes")

except Exception as e:
    print(f"   ✗ Fallo en la validación de la estructura del esquema: {e}")
    sys.exit(1)

# Test 9: Import URL configuration
print("\n9. Testeando la configuración de URL...")
try:
    from graphql_api.urls import urlpatterns

    assert len(urlpatterns) > 0, "No hay patrones de URL definidos"
    print("   ✓ Configuración de URL válida")
except Exception as e:
    print(f"   ✗ Fallo en la configuración de URL: {e}")
    sys.exit(1)

# Test 10: Comprobando la configuración de la aplicación
print("\n10. Testeando la configuración de la aplicación...")
try:
    from django.apps import apps

    graphql_app = apps.get_app_config("graphql_api")
    assert graphql_app is not None, "La aplicación GraphQL no está registrada"
    print("   ✓ La aplicación GraphQL está registrada exitosamente")

    gtfs_app = apps.get_app_config("gtfs")
    assert gtfs_app is not None, "La aplicación GTFS no está registrada"
    print("   ✓ La aplicación GTFS está registrada exitosamente")
except Exception as e:
    print(f"   ✗ Fallo en la configuración de la aplicación: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ Todas las comprobaciones de validación pasaron!")
print("=" * 60)
print("\nPróximos pasos:")
print("1. Ejecutar migraciones: python manage.py makemigrations && python manage.py migrate")
print("2. Crear un superusuario: python manage.py createsuperuser")
print("3. Ejecutar el servidor: python manage.py runserver")
print("4. Acceder a GraphQL en: http://localhost:8000/graphql/")
print("5. Ejecutar pruebas: pytest tests/test_graphql/")
print()
