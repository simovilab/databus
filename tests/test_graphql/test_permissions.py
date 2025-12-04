import pytest
from django.test import RequestFactory
from graphql_api.schema import schema
from strawberry.types import ExecutionContext


@pytest.mark.django_db
class TestPermissions:
    """Test GraphQL permissions and access control"""

    def setup_method(self):
        """Setup test client and request factory"""
        self.factory = RequestFactory()

    def execute_query(self, query, user=None, variables=None):
        """Helper to execute GraphQL queries"""
        request = self.factory.post("/graphql/")
        request.user = user
        context = ExecutionContext(context={"request": request}, operation_name=None)
        result = schema.execute_sync(
            query, variable_values=variables, context_value=context.context
        )
        return result

    def test_anonymous_user_cannot_query(self, feed):
        """Test that anonymous users cannot access queries"""
        query = """
        query {
            allFeeds {
                id
                name
            }
        }
        """
        result = self.execute_query(query, user=None)
        assert result.errors is not None
        assert "not authenticated" in str(result.errors[0]).lower()

    def test_authenticated_user_can_query(self, auth_user, feed):
        """Test that authenticated users can access queries"""
        query = """
        query {
            allFeeds {
                id
                name
            }
        }
        """
        result = self.execute_query(query, user=auth_user)
        assert result.errors is None
        assert result.data is not None

    def test_non_staff_user_cannot_mutate(self, auth_user, feed):
        """Test that non-staff users cannot perform mutations"""
        mutation = """
        mutation($input: CreateAgencyInput!) {
            createAgency(input: $input) {
                success
                errors
            }
        }
        """
        variables = {
            "input": {
                "feedId": feed.id,
                "agencyId": "TEST",
                "agencyName": "Test",
                "agencyUrl": "https://test.com",
                "agencyTimezone": "UTC",
            }
        }
        result = self.execute_query(mutation, user=auth_user, variables=variables)
        assert result.errors is not None
        assert "staff" in str(result.errors[0]).lower()

    def test_staff_user_can_mutate(self, staff_user, feed):
        """Test that staff users can perform mutations"""
        mutation = """
        mutation($input: CreateAgencyInput!) {
            createAgency(input: $input) {
                success
                errors
            }
        }
        """
        variables = {
            "input": {
                "feedId": feed.id,
                "agencyId": "STAFF_TEST",
                "agencyName": "Staff Test Agency",
                "agencyUrl": "https://stafftest.com",
                "agencyTimezone": "America/New_York",
            }
        }
        result = self.execute_query(mutation, user=staff_user, variables=variables)
        assert result.errors is None
        assert result.data["createAgency"]["success"] is True

    def test_multiple_queries_with_different_auth_states(
        self, auth_user, staff_user, feed
    ):
        """Test multiple queries with different authentication states"""
        query = """
        query {
            allFeeds {
                id
                name
            }
        }
        """

        # Anonymous - should fail
        result = self.execute_query(query, user=None)
        assert result.errors is not None

        # Authenticated - should succeed
        result = self.execute_query(query, user=auth_user)
        assert result.errors is None

        # Staff - should succeed
        result = self.execute_query(query, user=staff_user)
        assert result.errors is None

    def test_permission_error_message_format(self, feed):
        """Test that permission errors have proper format"""
        query = """
        query {
            allAgencies {
                edges {
                    agencyName
                }
            }
        }
        """
        result = self.execute_query(query, user=None)
        assert result.errors is not None
        assert len(result.errors) > 0
        error = result.errors[0]
        assert "authenticated" in str(error).lower()

    def test_partial_query_permissions(self, auth_user):
        """Test query with both permitted and non-permitted fields"""
        # All fields should be accessible to authenticated users in queries
        query = """
        query {
            allFeeds {
                id
                name
                url
                createdAt
            }
        }
        """
        result = self.execute_query(query, user=auth_user)
        assert result.errors is None

    def test_nested_query_permissions(self, auth_user, agency):
        """Test that permissions apply to nested queries"""
        query = """
        query($id: Int!) {
            agency(id: $id) {
                agencyName
                feed {
                    name
                }
            }
        }
        """
        result = self.execute_query(query, user=auth_user, variables={"id": agency.id})
        assert result.errors is None
        assert result.data["agency"]["feed"]["name"] is not None

    def test_anonymous_user_all_endpoints(self):
        """Test that anonymous users are blocked from all protected endpoints"""
        queries = [
            "query { allFeeds { id } }",
            "query { allAgencies { edges { id } } }",
            "query { allRoutes { edges { id } } }",
            "query { allStops { edges { id } } }",
        ]

        for query in queries:
            result = self.execute_query(query, user=None)
            assert result.errors is not None, f"Query should fail: {query}"
            assert "authenticated" in str(result.errors[0]).lower()

    def test_authenticated_user_all_read_endpoints(self, auth_user, feed):
        """Test that authenticated users can access all read endpoints"""
        queries = [
            "query { allFeeds { id } }",
            "query { allAgencies { edges { id } pageInfo { totalCount } } }",
            "query { allRoutes { edges { id } pageInfo { totalCount } } }",
            "query { allStops { edges { id } pageInfo { totalCount } } }",
        ]

        for query in queries:
            result = self.execute_query(query, user=auth_user)
            assert result.errors is None, f"Query should succeed: {query}"
            assert result.data is not None
