import pytest
from django.test import RequestFactory
from graphql_api.schema import schema
from strawberry.types import ExecutionContext


@pytest.mark.django_db
class TestQueries:
    """Test GraphQL queries"""

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

    def test_all_feeds_query_requires_auth(self):
        """Test that allFeeds query requires authentication"""
        query = """
        query {
            allFeeds {
                id
                name
                url
            }
        }
        """
        result = self.execute_query(query, user=None)
        assert result.errors is not None
        assert "not authenticated" in str(result.errors[0]).lower()

    def test_all_feeds_query_authenticated(self, auth_user, feed):
        """Test allFeeds query with authenticated user"""
        query = """
        query {
            allFeeds {
                id
                name
                url
            }
        }
        """
        result = self.execute_query(query, user=auth_user)
        assert result.errors is None
        assert result.data is not None
        assert "allFeeds" in result.data
        assert len(result.data["allFeeds"]) == 1
        assert result.data["allFeeds"][0]["name"] == "Test Feed"

    def test_feed_query_by_id(self, auth_user, feed):
        """Test feed query by ID"""
        query = """
        query($id: Int!) {
            feed(id: $id) {
                id
                name
                url
            }
        }
        """
        result = self.execute_query(query, user=auth_user, variables={"id": feed.id})
        assert result.errors is None
        assert result.data["feed"]["name"] == "Test Feed"

    def test_all_agencies_query(self, auth_user, agency):
        """Test allAgencies query"""
        query = """
        query {
            allAgencies {
                edges {
                    id
                    agencyName
                    agencyTimezone
                }
                pageInfo {
                    totalCount
                    hasNextPage
                    hasPreviousPage
                }
            }
        }
        """
        result = self.execute_query(query, user=auth_user)
        assert result.errors is None
        assert result.data["allAgencies"]["pageInfo"]["totalCount"] == 1
        assert (
            result.data["allAgencies"]["edges"][0]["agencyName"]
            == "Test Transit Agency"
        )

    def test_all_agencies_pagination(self, auth_user, multiple_agencies):
        """Test allAgencies query with pagination"""
        query = """
        query($offset: Int, $limit: Int) {
            allAgencies(offset: $offset, limit: $limit) {
                edges {
                    id
                    agencyName
                }
                pageInfo {
                    totalCount
                    hasNextPage
                    hasPreviousPage
                }
            }
        }
        """
        # First page
        result = self.execute_query(
            query, user=auth_user, variables={"offset": 0, "limit": 2}
        )
        assert result.errors is None
        assert len(result.data["allAgencies"]["edges"]) == 2
        assert result.data["allAgencies"]["pageInfo"]["totalCount"] == 5
        assert result.data["allAgencies"]["pageInfo"]["hasNextPage"] is True

        # Second page
        result = self.execute_query(
            query, user=auth_user, variables={"offset": 2, "limit": 2}
        )
        assert len(result.data["allAgencies"]["edges"]) == 2
        assert result.data["allAgencies"]["pageInfo"]["hasNextPage"] is True

    def test_all_agencies_filtering(self, auth_user, multiple_agencies):
        """Test allAgencies query with filtering"""
        query = """
        query($nameContains: String) {
            allAgencies(nameContains: $nameContains) {
                edges {
                    id
                    agencyName
                }
                pageInfo {
                    totalCount
                }
            }
        }
        """
        result = self.execute_query(
            query, user=auth_user, variables={"nameContains": "Agency 1"}
        )
        assert result.errors is None
        assert result.data["allAgencies"]["pageInfo"]["totalCount"] == 1
        assert "Agency 1" in result.data["allAgencies"]["edges"][0]["agencyName"]

    def test_agency_query_by_id(self, auth_user, agency):
        """Test agency query by ID"""
        query = """
        query($id: Int!) {
            agency(id: $id) {
                id
                agencyName
                agencyUrl
                agencyTimezone
            }
        }
        """
        result = self.execute_query(query, user=auth_user, variables={"id": agency.id})
        assert result.errors is None
        assert result.data["agency"]["agencyName"] == "Test Transit Agency"

    def test_all_routes_query(self, auth_user, route):
        """Test allRoutes query"""
        query = """
        query {
            allRoutes {
                edges {
                    id
                    routeShortName
                    routeLongName
                    routeType
                }
                pageInfo {
                    totalCount
                }
            }
        }
        """
        result = self.execute_query(query, user=auth_user)
        assert result.errors is None
        assert result.data["allRoutes"]["pageInfo"]["totalCount"] == 1
        assert result.data["allRoutes"]["edges"][0]["routeShortName"] == "1"

    def test_all_routes_filtering(self, auth_user, multiple_routes):
        """Test allRoutes query with filtering"""
        query = """
        query($routeType: Int) {
            allRoutes(routeType: $routeType) {
                edges {
                    routeShortName
                    routeType
                }
                pageInfo {
                    totalCount
                }
            }
        }
        """
        result = self.execute_query(query, user=auth_user, variables={"routeType": 3})
        assert result.errors is None
        assert result.data["allRoutes"]["pageInfo"]["totalCount"] == 10

    def test_all_stops_query(self, auth_user, stop):
        """Test allStops query"""
        query = """
        query {
            allStops {
                edges {
                    id
                    stopName
                    stopLat
                    stopLon
                }
                pageInfo {
                    totalCount
                }
            }
        }
        """
        result = self.execute_query(query, user=auth_user)
        assert result.errors is None
        assert result.data["allStops"]["pageInfo"]["totalCount"] == 1
        assert result.data["allStops"]["edges"][0]["stopName"] == "Main Street Station"

    def test_trips_by_route_query(self, auth_user, trip, route):
        """Test tripsByRoute query"""
        query = """
        query($routeId: Int!) {
            tripsByRoute(routeId: $routeId) {
                edges {
                    id
                    tripId
                    tripHeadsign
                    directionId
                }
                pageInfo {
                    totalCount
                }
            }
        }
        """
        result = self.execute_query(
            query, user=auth_user, variables={"routeId": route.id}
        )
        assert result.errors is None
        assert result.data["tripsByRoute"]["pageInfo"]["totalCount"] == 1
        assert result.data["tripsByRoute"]["edges"][0]["tripId"] == "TRIP_1"

    def test_stop_times_by_trip_query(self, auth_user, stop_time, trip):
        """Test stopTimesByTrip query"""
        query = """
        query($tripId: Int!) {
            stopTimesByTrip(tripId: $tripId) {
                edges {
                    id
                    stopSequence
                    arrivalTimeStr
                    departureTimeStr
                    stop {
                        stopName
                    }
                }
                pageInfo {
                    totalCount
                }
            }
        }
        """
        result = self.execute_query(
            query, user=auth_user, variables={"tripId": trip.id}
        )
        assert result.errors is None
        assert result.data["stopTimesByTrip"]["pageInfo"]["totalCount"] == 1
        assert result.data["stopTimesByTrip"]["edges"][0]["stopSequence"] == 1
        assert (
            result.data["stopTimesByTrip"]["edges"][0]["arrivalTimeStr"] == "08:30:00"
        )
        assert (
            result.data["stopTimesByTrip"]["edges"][0]["stop"]["stopName"]
            == "Main Street Station"
        )

    def test_query_without_authentication(self):
        """Test that queries without authentication are rejected"""
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
        assert "not authenticated" in str(result.errors[0]).lower()

    def test_nested_query(self, auth_user, trip, route, agency):
        """Test nested query with related objects"""
        query = """
        query($tripId: Int!) {
            trip(id: $tripId) {
                tripId
                tripHeadsign
                route {
                    routeShortName
                    routeLongName
                    agency {
                        agencyName
                    }
                }
            }
        }
        """
        result = self.execute_query(
            query, user=auth_user, variables={"tripId": trip.id}
        )
        assert result.errors is None
        assert result.data["trip"]["tripId"] == "TRIP_1"
        assert result.data["trip"]["route"]["routeShortName"] == "1"
        assert (
            result.data["trip"]["route"]["agency"]["agencyName"]
            == "Test Transit Agency"
        )
