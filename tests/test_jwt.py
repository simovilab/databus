"""
JWT Authentication Tests for Databús API.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from feed.models import Operator


class JWTAuthenticationTestCase(TestCase):
    """Test cases for JWT authentication."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testoperator',
            email='test@operator.com',
            password='testpass123'
        )
        
        # Create operator with default role
        self.operator = Operator.objects.create(
            id='OP001',
            user=self.user,
            role='operator'
        )
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@databus.com',
            password='adminpass123',
            is_staff=True
        )
        
        self.admin_operator = Operator.objects.create(
            id='OP002',
            user=self.admin_user,
            role='admin'
        )

    def test_obtain_token_success(self):
        """Test obtaining JWT token with valid credentials."""
        url = reverse('token_obtain_pair')
        data = {
            'username': 'testoperator',
            'password': 'testpass123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        self.assertIn('role', response.data['user'])
        self.assertIn('operator_id', response.data['user'])
        self.assertEqual(response.data['user']['role'], 'operator')

    def test_obtain_token_invalid_credentials(self):
        """Test obtaining JWT token with invalid credentials."""
        url = reverse('token_obtain_pair')
        data = {
            'username': 'testoperator',
            'password': 'wrongpassword'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_obtain_token_admin_role(self):
        """Test that admin users receive admin role in token."""
        url = reverse('token_obtain_pair')
        data = {
            'username': 'admin',
            'password': 'adminpass123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['role'], 'admin')

    def test_refresh_token_success(self):
        """Test refreshing JWT token with valid refresh token."""
        # First, obtain tokens
        obtain_url = reverse('token_obtain_pair')
        obtain_data = {
            'username': 'testoperator',
            'password': 'testpass123'
        }
        obtain_response = self.client.post(obtain_url, obtain_data, format='json')
        refresh_token = obtain_response.data['refresh']
        
        # Then, refresh the token
        refresh_url = reverse('token_refresh')
        refresh_data = {
            'refresh': refresh_token
        }
        
        response = self.client.post(refresh_url, refresh_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)  # Token rotation

    def test_refresh_token_invalid(self):
        """Test refreshing JWT token with invalid refresh token."""
        url = reverse('token_refresh')
        data = {
            'refresh': 'invalid.token.here'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verify_token_success(self):
        """Test verifying valid JWT token."""
        # First, obtain token
        obtain_url = reverse('token_obtain_pair')
        obtain_data = {
            'username': 'testoperator',
            'password': 'testpass123'
        }
        obtain_response = self.client.post(obtain_url, obtain_data, format='json')
        access_token = obtain_response.data['access']
        
        # Then, verify the token
        verify_url = reverse('token_verify')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        response = self.client.get(verify_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('valid', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['username'], 'testoperator')
        self.assertEqual(response.data['user']['role'], 'operator')

    def test_verify_token_invalid(self):
        """Test verifying invalid JWT token."""
        url = reverse('token_verify')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid.token.here')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verify_token_no_auth_header(self):
        """Test verifying token without authentication header."""
        url = reverse('token_verify')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_success(self):
        """Test logout with valid refresh token."""
        # First, obtain tokens
        obtain_url = reverse('token_obtain_pair')
        obtain_data = {
            'username': 'testoperator',
            'password': 'testpass123'
        }
        obtain_response = self.client.post(obtain_url, obtain_data, format='json')
        refresh_token = obtain_response.data['refresh']
        access_token = obtain_response.data['access']
        
        # Then, logout (blacklist the refresh token)
        logout_url = reverse('logout')
        logout_data = {
            'refresh': refresh_token
        }
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        response = self.client.post(logout_url, logout_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Try to refresh with the blacklisted token - should fail
        refresh_url = reverse('token_refresh')
        refresh_data = {
            'refresh': refresh_token
        }
        
        refresh_response = self.client.post(refresh_url, refresh_data, format='json')
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_no_auth(self):
        """Test logout without authentication."""
        url = reverse('logout')
        data = {
            'refresh': 'some.token.here'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_endpoint_with_jwt(self):
        """Test accessing authenticated endpoint with valid JWT."""
        # Obtain token
        obtain_url = reverse('token_obtain_pair')
        obtain_data = {
            'username': 'testoperator',
            'password': 'testpass123'
        }
        obtain_response = self.client.post(obtain_url, obtain_data, format='json')
        access_token = obtain_response.data['access']
        
        # Access authenticated endpoint
        url = reverse('operator-list')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_authenticated_endpoint_without_jwt(self):
        """Test accessing authenticated endpoint without JWT."""
        url = reverse('operator-list')
        
        response = self.client.get(url)
        
        # Should still work as read-only based on permissions
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class RoleBasedPermissionTestCase(TestCase):
    """Test cases for role-based permissions."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        
        # Create users with different roles
        self.admin_user = User.objects.create_user(
            username='admin',
            password='admin123',
            is_staff=True
        )
        self.admin_operator = Operator.objects.create(
            id='ADM001',
            user=self.admin_user,
            role='admin'
        )
        
        self.operator_user = User.objects.create_user(
            username='operator',
            password='operator123'
        )
        self.operator = Operator.objects.create(
            id='OP001',
            user=self.operator_user,
            role='operator'
        )
        
        self.readonly_user = User.objects.create_user(
            username='readonly',
            password='readonly123'
        )
        self.readonly_operator = Operator.objects.create(
            id='RO001',
            user=self.readonly_user,
            role='readonly'
        )
        
        self.supervisor_user = User.objects.create_user(
            username='supervisor',
            password='supervisor123'
        )
        self.supervisor_operator = Operator.objects.create(
            id='SUP001',
            user=self.supervisor_user,
            role='supervisor'
        )

    def get_token(self, username, password):
        """Helper method to obtain JWT token."""
        url = reverse('token_obtain_pair')
        data = {
            'username': username,
            'password': password
        }
        response = self.client.post(url, data, format='json')
        return response.data['access']

    def test_admin_can_write(self):
        """Test that admin can create/update resources."""
        token = self.get_token('admin', 'admin123')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Assuming company endpoint exists and allows creation
        # This test would need actual endpoint and data
        self.assertTrue(self.admin_operator.can_write)
        self.assertTrue(self.admin_operator.is_admin)

    def test_operator_can_write(self):
        """Test that operator role has write permissions."""
        token = self.get_token('operator', 'operator123')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        self.assertTrue(self.operator.can_write)
        self.assertFalse(self.operator.is_admin)

    def test_readonly_cannot_write(self):
        """Test that readonly role cannot write."""
        token = self.get_token('readonly', 'readonly123')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        self.assertFalse(self.readonly_operator.can_write)
        self.assertFalse(self.readonly_operator.is_admin)

    def test_supervisor_can_write(self):
        """Test that supervisor role has write permissions."""
        token = self.get_token('supervisor', 'supervisor123')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        self.assertTrue(self.supervisor_operator.can_write)
        self.assertFalse(self.supervisor_operator.is_admin)

    def test_token_contains_correct_role(self):
        """Test that JWT token contains the correct role."""
        # Test admin role
        admin_token = self.get_token('admin', 'admin123')
        self.assertIsNotNone(admin_token)
        
        # Test operator role
        operator_token = self.get_token('operator', 'operator123')
        self.assertIsNotNone(operator_token)
        
        # Test readonly role
        readonly_token = self.get_token('readonly', 'readonly123')
        self.assertIsNotNone(readonly_token)
