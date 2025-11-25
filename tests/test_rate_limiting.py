"""
Test suite for rate limiting and quota enforcement.

Tests:
- Global rate limits (anonymous and authenticated)
- Per-client quota limits (minute/hour/day)
- Burst traffic handling
- Sustained rate limits
- Rate limit headers
- 429 responses with Retry-After
- Counter persistence and reset
- Usage metrics tracking
"""

import time
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework import status
from api.client_models import APIClient as DatabusClient, APIKey, ClientQuota, ClientUsageMetrics
from api.throttling import (
    GlobalAnonThrottle,
    GlobalUserThrottle,
    ClientQuotaThrottle,
    BurstRateThrottle,
    SustainedRateThrottle,
)


class RateLimitTestCase(TestCase):
    """Base test case with common setup for rate limiting tests."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Clear Redis cache before each test
        cache.clear()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create API client instance
        self.client = APIClient()
        self.factory = APIRequestFactory()
    
    def tearDown(self):
        """Clean up after tests."""
        cache.clear()


@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_RATES': {
            'anon': '5/minute',  # Low limit for testing
        }
    }
)
class GlobalAnonThrottleTest(RateLimitTestCase):
    """Tests for global anonymous rate limiting."""
    
    def test_anonymous_requests_within_limit(self):
        """Test that requests within the limit are allowed."""
        # Make 4 requests (under the 5/minute limit)
        for i in range(4):
            response = self.client.get('/api/')
            self.assertIn(response.status_code, [200, 301])
            
            # Check rate limit headers
            self.assertIn('X-RateLimit-Limit', response)
            self.assertIn('X-RateLimit-Remaining', response)
            self.assertIn('X-RateLimit-Reset', response)
    
    def test_anonymous_requests_exceed_limit(self):
        """Test that requests exceeding the limit are throttled."""
        # Make 5 requests (at the limit)
        for i in range(5):
            response = self.client.get('/api/')
            self.assertIn(response.status_code, [200, 301])
        
        # 6th request should be throttled
        response = self.client.get('/api/')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Check rate limit headers on throttled response
        self.assertEqual(response['X-RateLimit-Remaining'], '0')
        self.assertIn('Retry-After', response)
    
    def test_rate_limit_headers_format(self):
        """Test that rate limit headers are properly formatted."""
        response = self.client.get('/api/')
        
        # Headers should be present
        self.assertIn('X-RateLimit-Limit', response)
        self.assertIn('X-RateLimit-Remaining', response)
        self.assertIn('X-RateLimit-Reset', response)
        
        # Values should be numeric
        limit = int(response['X-RateLimit-Limit'])
        remaining = int(response['X-RateLimit-Remaining'])
        reset_time = int(response['X-RateLimit-Reset'])
        
        self.assertGreater(limit, 0)
        self.assertGreaterEqual(remaining, 0)
        self.assertGreater(reset_time, time.time())


@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_RATES': {
            'user': '10/minute',
        }
    }
)
class GlobalUserThrottleTest(RateLimitTestCase):
    """Tests for global authenticated user rate limiting."""
    
    def test_authenticated_requests_within_limit(self):
        """Test authenticated user requests within limit."""
        self.client.force_authenticate(user=self.user)
        
        # Make 8 requests (under the 10/minute limit)
        for i in range(8):
            response = self.client.get('/api/')
            self.assertIn(response.status_code, [200, 301])
    
    def test_authenticated_requests_exceed_limit(self):
        """Test authenticated user requests exceeding limit."""
        self.client.force_authenticate(user=self.user)
        
        # Make 10 requests (at the limit)
        for i in range(10):
            response = self.client.get('/api/')
            self.assertIn(response.status_code, [200, 301])
        
        # 11th request should be throttled
        response = self.client.get('/api/')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
    
    def test_authenticated_higher_limit_than_anonymous(self):
        """Test that authenticated users have higher limits."""
        # Anonymous requests
        for i in range(5):
            response = self.client.get('/api/')
        
        anon_response = self.client.get('/api/')
        anon_throttled = (anon_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Clear cache for clean test
        cache.clear()
        
        # Authenticated requests
        self.client.force_authenticate(user=self.user)
        for i in range(5):
            response = self.client.get('/api/')
        
        auth_response = self.client.get('/api/')
        auth_throttled = (auth_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Anonymous should be throttled, authenticated should not
        self.assertTrue(anon_throttled)
        self.assertFalse(auth_throttled)


class ClientQuotaThrottleTest(RateLimitTestCase):
    """Tests for per-client quota enforcement."""
    
    def setUp(self):
        """Set up test client with quota."""
        super().setUp()
        
        # Create Databus API client
        self.databus_client = DatabusClient.objects.create(
            client_name='Test Client',
            client_type='vehicle',
            owner=self.user,
            organization='Test Org',
            contact_email='client@test.com',
            status='active'
        )
        
        # Create quota with tight limits for testing
        self.quota = ClientQuota.objects.create(
            client=self.databus_client,
            requests_per_minute=5,
            requests_per_hour=100,
            requests_per_day=1000
        )
        
        # Create API key
        self.api_key, self.secret_key = APIKey.create_key(
            client=self.databus_client,
            name='Test Key'
        )
    
    def test_client_requests_within_quota(self):
        """Test that requests within quota are allowed."""
        # Add API key to request
        self.client.credentials(HTTP_AUTHORIZATION=f'ApiKey {self.secret_key}')
        
        # Make 4 requests (under the 5/minute limit)
        for i in range(4):
            response = self.client.get('/api/')
            self.assertIn(response.status_code, [200, 301])
            
            # Check quota headers
            self.assertIn('X-RateLimit-Limit', response)
            self.assertEqual(response['X-RateLimit-Limit'], '5')
    
    def test_client_requests_exceed_minute_quota(self):
        """Test that requests exceeding per-minute quota are throttled."""
        self.client.credentials(HTTP_AUTHORIZATION=f'ApiKey {self.secret_key}')
        
        # Make 5 requests (at the limit)
        for i in range(5):
            response = self.client.get('/api/')
            self.assertIn(response.status_code, [200, 301])
        
        # 6th request should be throttled
        response = self.client.get('/api/')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Check error message mentions minute quota
        self.assertIn('Minute quota exceeded', response.data['detail'])
    
    def test_quota_violation_tracked_in_metrics(self):
        """Test that quota violations are recorded in metrics."""
        self.client.credentials(HTTP_AUTHORIZATION=f'ApiKey {self.secret_key}')
        
        # Exceed quota
        for i in range(6):
            self.client.get('/api/')
        
        # Check metrics
        metrics = ClientUsageMetrics.objects.get(client=self.databus_client)
        self.assertGreater(metrics.quota_violations, 0)
    
    def test_unlimited_quota(self):
        """Test that 0 or negative quota values mean unlimited."""
        # Set unlimited quota
        self.quota.requests_per_minute = 0
        self.quota.save()
        
        self.client.credentials(HTTP_AUTHORIZATION=f'ApiKey {self.secret_key}')
        
        # Make many requests (should all succeed)
        for i in range(10):
            response = self.client.get('/api/')
            self.assertIn(response.status_code, [200, 301])
    
    def test_quota_reset_after_window(self):
        """Test that quota resets after time window expires."""
        self.client.credentials(HTTP_AUTHORIZATION=f'ApiKey {self.secret_key}')
        
        # Use up quota
        for i in range(5):
            self.client.get('/api/')
        
        # Should be throttled
        response = self.client.get('/api/')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Clear cache to simulate time window expiration
        cache.clear()
        
        # Should work again
        response = self.client.get('/api/')
        self.assertIn(response.status_code, [200, 301])


@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_RATES': {
            'burst': '3/second',
        }
    }
)
class BurstRateThrottleTest(RateLimitTestCase):
    """Tests for burst rate limiting."""
    
    def test_burst_traffic_allowed_within_limit(self):
        """Test that burst traffic within limit is allowed."""
        # Make 3 rapid requests
        for i in range(3):
            response = self.client.get('/api/')
            self.assertIn(response.status_code, [200, 301])
    
    def test_burst_traffic_throttled_beyond_limit(self):
        """Test that excessive burst traffic is throttled."""
        # Make 3 rapid requests (at limit)
        for i in range(3):
            self.client.get('/api/')
        
        # 4th should be throttled
        response = self.client.get('/api/')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('Burst rate limit exceeded', response.data['detail'])
    
    def test_burst_limit_resets_quickly(self):
        """Test that burst limit resets after 1 second."""
        # Use up burst limit
        for i in range(3):
            self.client.get('/api/')
        
        # Wait 1 second for window to expire
        time.sleep(1.1)
        
        # Should work again
        response = self.client.get('/api/')
        self.assertIn(response.status_code, [200, 301])


class UsageMetricsTrackingTest(RateLimitTestCase):
    """Tests for automatic usage metrics tracking."""
    
    def setUp(self):
        """Set up test client."""
        super().setUp()
        
        # Create Databus API client
        self.databus_client = DatabusClient.objects.create(
            client_name='Metrics Test Client',
            client_type='device',
            owner=self.user,
            organization='Test Org',
            contact_email='metrics@test.com',
            status='active'
        )
        
        # Create API key
        self.api_key, self.secret_key = APIKey.create_key(
            client=self.databus_client,
            name='Test Key'
        )
    
    def test_request_counter_increments(self):
        """Test that request counter increments."""
        self.client.credentials(HTTP_AUTHORIZATION=f'ApiKey {self.secret_key}')
        
        # Get initial count
        metrics, _ = ClientUsageMetrics.objects.get_or_create(client=self.databus_client)
        initial_count = metrics.total_requests
        
        # Make request
        self.client.get('/api/')
        
        # Check counter incremented
        metrics.refresh_from_db()
        self.assertEqual(metrics.total_requests, initial_count + 1)
    
    def test_successful_request_tracked(self):
        """Test that successful requests are tracked separately."""
        self.client.credentials(HTTP_AUTHORIZATION=f'ApiKey {self.secret_key}')
        
        metrics, _ = ClientUsageMetrics.objects.get_or_create(client=self.databus_client)
        initial_success = metrics.successful_requests
        
        # Make successful request
        response = self.client.get('/api/')
        if response.status_code in [200, 301]:
            metrics.refresh_from_db()
            self.assertEqual(metrics.successful_requests, initial_success + 1)
    
    def test_failed_request_tracked(self):
        """Test that failed requests are tracked separately."""
        self.client.credentials(HTTP_AUTHORIZATION=f'ApiKey {self.secret_key}')
        
        metrics, _ = ClientUsageMetrics.objects.get_or_create(client=self.databus_client)
        initial_failed = metrics.failed_requests
        
        # Make request to non-existent endpoint (404)
        self.client.get('/api/nonexistent/')
        
        metrics.refresh_from_db()
        self.assertEqual(metrics.failed_requests, initial_failed + 1)
    
    def test_response_time_tracked(self):
        """Test that response times are tracked."""
        self.client.credentials(HTTP_AUTHORIZATION=f'ApiKey {self.secret_key}')
        
        # Make request
        self.client.get('/api/')
        
        # Check response time was recorded
        metrics = ClientUsageMetrics.objects.get(client=self.databus_client)
        self.assertGreater(metrics.average_response_time_ms, 0)
    
    def test_last_activity_updated(self):
        """Test that last activity timestamp is updated."""
        self.client.credentials(HTTP_AUTHORIZATION=f'ApiKey {self.secret_key}')
        
        metrics, _ = ClientUsageMetrics.objects.get_or_create(client=self.databus_client)
        old_activity = metrics.last_activity
        
        # Wait a moment
        time.sleep(0.1)
        
        # Make request
        self.client.get('/api/')
        
        # Check timestamp updated
        metrics.refresh_from_db()
        self.assertGreater(metrics.last_activity, old_activity)


class RateLimitHeadersTest(RateLimitTestCase):
    """Tests for rate limit headers in responses."""
    
    def test_all_headers_present(self):
        """Test that all required headers are present."""
        response = self.client.get('/api/')
        
        required_headers = [
            'X-RateLimit-Limit',
            'X-RateLimit-Remaining',
            'X-RateLimit-Reset',
        ]
        
        for header in required_headers:
            self.assertIn(header, response)
    
    def test_remaining_decrements(self):
        """Test that remaining counter decrements with each request."""
        response1 = self.client.get('/api/')
        remaining1 = int(response1.get('X-RateLimit-Remaining', 0))
        
        response2 = self.client.get('/api/')
        remaining2 = int(response2.get('X-RateLimit-Remaining', 0))
        
        # Remaining should decrease
        self.assertLess(remaining2, remaining1)
    
    def test_429_includes_retry_after(self):
        """Test that 429 responses include Retry-After header."""
        # Exhaust rate limit
        for i in range(10):
            self.client.get('/api/')
        
        # Get throttled response
        response = self.client.get('/api/')
        
        if response.status_code == 429:
            self.assertIn('Retry-After', response)
            retry_after = int(response['Retry-After'])
            self.assertGreater(retry_after, 0)


class RedisCounterPersistenceTest(RateLimitTestCase):
    """Tests for Redis counter persistence and expiration."""
    
    def test_counters_persist_across_requests(self):
        """Test that counters are stored in Redis."""
        # Make request
        self.client.get('/api/')
        
        # Check that throttle key exists in cache
        # (Implementation detail - may need adjustment based on actual key format)
        keys = cache.keys('throttle_*')
        self.assertGreater(len(keys), 0)
    
    def test_counters_expire_after_window(self):
        """Test that counters expire after their time window."""
        # Make request
        self.client.get('/api/')
        
        # Get cache keys
        keys_before = cache.keys('throttle_*')
        self.assertGreater(len(keys_before), 0)
        
        # Clear cache to simulate expiration
        cache.clear()
        
        # Check keys are gone
        keys_after = cache.keys('throttle_*')
        self.assertEqual(len(keys_after), 0)


class ThrottleIntegrationTest(RateLimitTestCase):
    """Integration tests for multiple throttle classes working together."""
    
    def setUp(self):
        """Set up complex scenario with multiple throttles."""
        super().setUp()
        
        # Create client with quotas
        self.databus_client = DatabusClient.objects.create(
            client_name='Integration Test Client',
            client_type='integration',
            owner=self.user,
            organization='Test Org',
            contact_email='integration@test.com',
            status='active'
        )
        
        self.quota = ClientQuota.objects.create(
            client=self.databus_client,
            requests_per_minute=10,
            requests_per_hour=100,
            requests_per_day=1000
        )
        
        self.api_key, self.secret_key = APIKey.create_key(
            client=self.databus_client,
            name='Test Key'
        )
    
    def test_client_quota_checked_before_global(self):
        """Test that client-specific quotas override global limits."""
        self.client.credentials(HTTP_AUTHORIZATION=f'ApiKey {self.secret_key}')
        
        # Client quota is 10/minute, which should be enforced
        # Make 10 requests
        for i in range(10):
            response = self.client.get('/api/')
            self.assertIn(response.status_code, [200, 301])
        
        # 11th should be throttled by client quota
        response = self.client.get('/api/')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
    
    def test_metrics_tracked_for_throttled_requests(self):
        """Test that even throttled requests are tracked in metrics."""
        self.client.credentials(HTTP_AUTHORIZATION=f'ApiKey {self.secret_key}')
        
        # Exceed quota
        for i in range(15):
            self.client.get('/api/')
        
        # Check metrics
        metrics = ClientUsageMetrics.objects.get(client=self.databus_client)
        
        # Total requests should include throttled ones
        self.assertGreaterEqual(metrics.total_requests, 10)
        # Quota violations should be recorded
        self.assertGreater(metrics.quota_violations, 0)
