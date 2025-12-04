import pytest
from graphql_api.schema import schema


@pytest.mark.django_db
class TestSchema:
    """Test GraphQL schema structure"""

    def test_schema_loads_successfully(self):
        """Test that schema can be loaded without errors"""
        assert schema is not None
        assert hasattr(schema, "query_type")
        assert hasattr(schema, "mutation_type")

    def test_query_type_exists(self):
        """Test that Query type is defined"""
        query_type = schema.query_type
        assert query_type is not None
        assert query_type.name == "Query"

    def test_mutation_type_exists(self):
        """Test that Mutation type is defined"""
        mutation_type = schema.mutation_type
        assert mutation_type is not None
        assert mutation_type.name == "Mutation"

    def test_query_fields_exist(self):
        """Test that expected query fields are present"""
        query_type = schema.query_type
        field_names = [field.name for field in query_type.fields]

        expected_fields = [
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

        for field in expected_fields:
            assert field in field_names, f"Field {field} not found in Query type"

    def test_mutation_fields_exist(self):
        """Test that expected mutation fields are present"""
        mutation_type = schema.mutation_type
        field_names = [field.name for field in mutation_type.fields]

        expected_mutations = ["createAgency"]

        for mutation in expected_mutations:
            assert mutation in field_names, (
                f"Mutation {mutation} not found in Mutation type"
            )

    def test_types_are_registered(self):
        """Test that custom types are registered in schema"""
        type_map = schema.schema_converter.type_map

        expected_types = [
            "AgencyType",
            "RouteType",
            "StopType",
            "TripType",
            "StopTimeType",
            "FeedType",
            "PageInfo",
            "AgencyConnection",
            "RouteConnection",
            "StopConnection",
            "TripConnection",
            "StopTimeConnection",
        ]

        for type_name in expected_types:
            # Check if type exists in schema (Strawberry may modify names)
            assert any(
                type_name.lower() in str(t).lower() for t in type_map.values()
            ), f"Type {type_name} not found in schema"
