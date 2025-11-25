"""
Contract tests for OpenAPI schema validation.

Validates API responses against OpenAPI specification.
"""
import pytest
import json
from django.urls import reverse
from openapi_spec_validator import validate_spec
from openapi_spec_validator.readers import read_from_filename
import yaml


@pytest.mark.contract
class TestOpenAPISchema:
    """Tests for OpenAPI schema validity."""
    
    def test_openapi_schema_exists(self):
        """Test that OpenAPI schema file exists."""
        import os
        schema_path = '/home/hfarulla/databus/docs/API.json'
        assert os.path.exists(schema_path), "OpenAPI schema file not found"
    
    def test_openapi_schema_valid(self):
        """Test that OpenAPI schema is valid."""
        schema_path = '/home/hfarulla/databus/docs/API.json'
        
        try:
            with open(schema_path, 'r') as f:
                spec_dict = json.load(f)
            
            # Validate the schema
            validate_spec(spec_dict)
        except Exception as e:
            pytest.fail(f"OpenAPI schema validation failed: {e}")
    
    def test_openapi_version(self):
        """Test OpenAPI version is 3.x."""
        schema_path = '/home/hfarulla/databus/docs/API.json'
        
        with open(schema_path, 'r') as f:
            spec_dict = json.load(f)
        
        assert 'openapi' in spec_dict
        assert spec_dict['openapi'].startswith('3.')


@pytest.mark.contract
@pytest.mark.integration
class TestAPIClientContract:
    """Contract tests for API Client endpoints."""
    
    def test_list_clients_response_schema(self, authenticated_client, api_client_model):
        """Test list clients response matches schema."""
        url = reverse('api:client-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert isinstance(data, list) or 'results' in data
        
        if isinstance(data, list):
            items = data
        else:
            items = data['results']
        
        if len(items) > 0:
            client = items[0]
            assert 'id' in client
            assert 'client_name' in client
            assert 'client_type' in client
            assert 'contact_email' in client
            assert 'status' in client
    
    def test_create_client_request_schema(self, authenticated_client):
        """Test create client request follows schema."""
        url = reverse('api:client-list')
        
        # Valid request according to schema
        data = {
            'client_name': 'Contract Test Client',
            'client_type': 'vehicle',
            'contact_email': 'contract@example.com',
            'organization': 'Test Org',
            'status': 'pending'
        }
        
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code in [200, 201]
    
    def test_create_client_invalid_type(self, authenticated_client):
        """Test invalid client_type is rejected."""
        url = reverse('api:client-list')
        
        # Invalid client_type
        data = {
            'client_name': 'Bad Type Client',
            'client_type': 'invalid_type',
            'contact_email': 'bad@example.com',
            'status': 'pending'
        }
        
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == 400
        assert 'client_type' in response.json()


@pytest.mark.contract
@pytest.mark.integration
class TestAPIKeyContract:
    """Contract tests for API Key endpoints."""
    
    def test_create_apikey_response_schema(self, authenticated_client, api_client_model):
        """Test create API key response includes key."""
        from datetime import timedelta
        from django.utils import timezone
        
        url = reverse('api:apikey-list')
        data = {
            'client': api_client_model.id,
            'name': 'Contract Test Key',
            'expires_at': (timezone.now() + timedelta(days=30)).isoformat()
        }
        
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code in [200, 201]
        
        response_data = response.json()
        assert 'key' in response_data
        assert 'name' in response_data
        assert 'expires_at' in response_data
        assert 'is_active' in response_data


@pytest.mark.contract
@pytest.mark.integration
class TestErrorResponseContract:
    """Contract tests for error responses."""
    
    def test_401_unauthorized_format(self, api_client):
        """Test 401 error response format."""
        url = reverse('api:client-list')
        response = api_client.get(url)
        
        assert response.status_code == 401
        data = response.json()
        
        # DRF standard error format
        assert 'detail' in data or 'error' in data
    
    def test_404_not_found_format(self, authenticated_client):
        """Test 404 error response format."""
        url = reverse('api:client-detail', kwargs={'pk': 999999})
        response = authenticated_client.get(url)
        
        assert response.status_code == 404
        data = response.json()
        
        assert 'detail' in data or 'error' in data
    
    def test_400_bad_request_format(self, authenticated_client):
        """Test 400 error response format."""
        url = reverse('api:client-list')
        
        # Missing required fields
        data = {
            'client_name': 'Incomplete Client'
        }
        
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == 400
        
        response_data = response.json()
        # Should contain field-level errors
        assert isinstance(response_data, dict)


@pytest.mark.contract
class TestContentTypeHeaders:
    """Contract tests for Content-Type headers."""
    
    def test_json_content_type(self, authenticated_client, api_client_model):
        """Test responses have correct Content-Type."""
        url = reverse('api:client-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert 'application/json' in response['Content-Type']
    
    def test_accept_json(self, authenticated_client):
        """Test API accepts JSON requests."""
        url = reverse('api:client-list')
        
        data = {
            'client_name': 'JSON Test',
            'client_type': 'vehicle',
            'contact_email': 'json@example.com',
            'status': 'pending'
        }
        
        response = authenticated_client.post(
            url, 
            data, 
            format='json',
            HTTP_ACCEPT='application/json'
        )
        
        assert response.status_code in [200, 201]


@pytest.mark.contract
class TestPaginationContract:
    """Contract tests for pagination."""
    
    def test_pagination_structure(self, authenticated_client, db):
        """Test paginated responses have correct structure."""
        from api.models import APIClient
        
        # Create multiple clients to trigger pagination
        for i in range(15):
            APIClient.objects.create(
                client_name=f'Pagination Test {i}',
                client_type='vehicle',
                contact_email=f'page{i}@example.com',
                status='active'
            )
        
        url = reverse('api:client-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check pagination fields (DRF PageNumberPagination)
        if isinstance(data, dict):
            assert 'results' in data
            # Might also have: count, next, previous
            if 'count' in data:
                assert isinstance(data['count'], int)
            if 'next' in data:
                assert data['next'] is None or isinstance(data['next'], str)
            if 'previous' in data:
                assert data['previous'] is None or isinstance(data['previous'], str)


@pytest.mark.contract
class TestAuthenticationContract:
    """Contract tests for authentication."""
    
    def test_jwt_token_structure(self, api_client, user):
        """Test JWT token response structure."""
        url = reverse('token_obtain_pair')
        
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        
        response = api_client.post(url, data, format='json')
        assert response.status_code == 200
        
        response_data = response.json()
        assert 'access' in response_data
        assert 'refresh' in response_data
        
        # Tokens should be strings (JWT format)
        assert isinstance(response_data['access'], str)
        assert isinstance(response_data['refresh'], str)
    
    def test_bearer_token_authentication(self, api_client, jwt_token):
        """Test Bearer token authentication works."""
        url = reverse('api:client-list')
        
        # Without token
        response = api_client.get(url)
        assert response.status_code == 401
        
        # With token
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {jwt_token["access"]}')
        response = api_client.get(url)
        assert response.status_code == 200
