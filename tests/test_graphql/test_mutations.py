import pytest
from django.test import RequestFactory
from graphql_api.schema import schema
from strawberry.types import ExecutionContext
from gtfs.models import Agency


@pytest.mark.django_db
class TestMutations:
    """Test GraphQL mutations"""

    def setup_method(self):
        """Setup test client and request factory"""
        self.factory = RequestFactory()

    def execute_mutation(self, mutation, user=None, variables=None):
        """Helper to execute GraphQL mutations"""
        request = self.factory.post("/graphql/")
        request.user = user
        context = ExecutionContext(context={"request": request}, operation_name=None)
        result = schema.execute_sync(
            mutation, variable_values=variables, context_value=context.context
        )
        return result

    def test_create_agency_mutation_requires_staff(self, auth_user, feed):
        """Test that createAgency mutation requires staff permission"""
        mutation = """
        mutation($input: CreateAgencyInput!) {
            createAgency(input: $input) {
                success
                errors
                agency {
                    agencyName
                }
            }
        }
        """
        variables = {
            "input": {
                "feedId": feed.id,
                "agencyId": "NEW_AGENCY",
                "agencyName": "New Agency",
                "agencyUrl": "https://newagency.com",
                "agencyTimezone": "America/New_York",
            }
        }
        result = self.execute_mutation(mutation, user=auth_user, variables=variables)
        assert result.errors is not None
        assert "staff" in str(result.errors[0]).lower()

    def test_create_agency_mutation_anonymous(self, feed):
        """Test that createAgency mutation requires authentication"""
        mutation = """
        mutation($input: CreateAgencyInput!) {
            createAgency(input: $input) {
                success
                errors
                agency {
                    agencyName
                }
            }
        }
        """
        variables = {
            "input": {
                "feedId": feed.id,
                "agencyId": "NEW_AGENCY",
                "agencyName": "New Agency",
                "agencyUrl": "https://newagency.com",
                "agencyTimezone": "America/New_York",
            }
        }
        result = self.execute_mutation(mutation, user=None, variables=variables)
        assert result.errors is not None

    def test_create_agency_mutation_success(self, staff_user, feed):
        """Test successful agency creation"""
        mutation = """
        mutation($input: CreateAgencyInput!) {
            createAgency(input: $input) {
                success
                errors
                agency {
                    id
                    agencyId
                    agencyName
                    agencyUrl
                    agencyTimezone
                }
            }
        }
        """
        variables = {
            "input": {
                "feedId": feed.id,
                "agencyId": "NEW_AGENCY",
                "agencyName": "New Transit Agency",
                "agencyUrl": "https://newtransit.com",
                "agencyTimezone": "America/New_York",
                "agencyLang": "en",
                "agencyPhone": "555-1234",
            }
        }
        result = self.execute_mutation(mutation, user=staff_user, variables=variables)
        assert result.errors is None
        assert result.data["createAgency"]["success"] is True
        assert result.data["createAgency"]["errors"] == []
        assert (
            result.data["createAgency"]["agency"]["agencyName"] == "New Transit Agency"
        )
        assert (
            result.data["createAgency"]["agency"]["agencyTimezone"]
            == "America/New_York"
        )

        # Verify agency was created in database
        agency = Agency.objects.get(agency_id="NEW_AGENCY")
        assert agency.agency_name == "New Transit Agency"
        assert agency.agency_phone == "555-1234"

    def test_create_agency_mutation_missing_required_field(self, staff_user, feed):
        """Test agency creation with missing required field"""
        mutation = """
        mutation($input: CreateAgencyInput!) {
            createAgency(input: $input) {
                success
                errors
                agency {
                    agencyName
                }
            }
        }
        """
        variables = {
            "input": {
                "feedId": feed.id,
                "agencyId": "INVALID",
                "agencyName": "",  # Empty name
                "agencyUrl": "https://test.com",
                "agencyTimezone": "America/New_York",
            }
        }
        result = self.execute_mutation(mutation, user=staff_user, variables=variables)
        assert result.errors is None
        assert result.data["createAgency"]["success"] is False
        assert len(result.data["createAgency"]["errors"]) > 0
        assert "name" in result.data["createAgency"]["errors"][0].lower()

    def test_create_agency_mutation_invalid_feed(self, staff_user):
        """Test agency creation with non-existent feed"""
        mutation = """
        mutation($input: CreateAgencyInput!) {
            createAgency(input: $input) {
                success
                errors
                agency {
                    agencyName
                }
            }
        }
        """
        variables = {
            "input": {
                "feedId": 99999,  # Non-existent feed
                "agencyId": "TEST",
                "agencyName": "Test Agency",
                "agencyUrl": "https://test.com",
                "agencyTimezone": "America/New_York",
            }
        }
        result = self.execute_mutation(mutation, user=staff_user, variables=variables)
        assert result.errors is None
        assert result.data["createAgency"]["success"] is False
        assert len(result.data["createAgency"]["errors"]) > 0
        assert "feed" in result.data["createAgency"]["errors"][0].lower()

    def test_create_agency_mutation_duplicate(self, staff_user, feed, agency):
        """Test agency creation with duplicate agency_id"""
        mutation = """
        mutation($input: CreateAgencyInput!) {
            createAgency(input: $input) {
                success
                errors
                agency {
                    agencyName
                }
            }
        }
        """
        variables = {
            "input": {
                "feedId": feed.id,
                "agencyId": "TEST_AGENCY",  # Same as existing agency
                "agencyName": "Duplicate Agency",
                "agencyUrl": "https://duplicate.com",
                "agencyTimezone": "America/New_York",
            }
        }
        result = self.execute_mutation(mutation, user=staff_user, variables=variables)
        assert result.errors is None
        assert result.data["createAgency"]["success"] is False
        assert len(result.data["createAgency"]["errors"]) > 0
        assert "already exists" in result.data["createAgency"]["errors"][0].lower()

    def test_create_agency_mutation_with_optional_fields(self, staff_user, feed):
        """Test agency creation with all optional fields"""
        mutation = """
        mutation($input: CreateAgencyInput!) {
            createAgency(input: $input) {
                success
                errors
                agency {
                    agencyId
                    agencyName
                    agencyLang
                    agencyPhone
                    agencyEmail
                }
            }
        }
        """
        variables = {
            "input": {
                "feedId": feed.id,
                "agencyId": "FULL_AGENCY",
                "agencyName": "Complete Agency",
                "agencyUrl": "https://complete.com",
                "agencyTimezone": "Europe/London",
                "agencyLang": "es",
                "agencyPhone": "555-9999",
                "agencyFareUrl": "https://complete.com/fares",
                "agencyEmail": "info@complete.com",
            }
        }
        result = self.execute_mutation(mutation, user=staff_user, variables=variables)
        assert result.errors is None
        assert result.data["createAgency"]["success"] is True
        assert result.data["createAgency"]["agency"]["agencyLang"] == "es"
        assert result.data["createAgency"]["agency"]["agencyPhone"] == "555-9999"
        assert (
            result.data["createAgency"]["agency"]["agencyEmail"] == "info@complete.com"
        )

    def test_create_agency_mutation_validation_errors(self, staff_user, feed):
        """Test multiple validation errors"""
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
                "agencyId": "INVALID",
                "agencyName": "",  # Invalid
                "agencyUrl": "",  # Invalid
                "agencyTimezone": "",  # Invalid
            }
        }
        result = self.execute_mutation(mutation, user=staff_user, variables=variables)
        assert result.errors is None
        assert result.data["createAgency"]["success"] is False
        # Should have multiple errors
        assert len(result.data["createAgency"]["errors"]) >= 3
