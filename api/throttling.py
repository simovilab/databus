"""
Rate limiting and throttling for Databús API.

Implements:
- Global rate limits (anonymous and authenticated users)
- Per-client rate limits (based on APIClient quotas)
- Redis-backed counters for persistence
- Standard rate limit headers (X-RateLimit-*)
- 429 responses with Retry-After header
"""

import time
from django.core.cache import cache
from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle, AnonRateThrottle, UserRateThrottle
from rest_framework.exceptions import Throttled
from api.client_models import APIClient, ClientQuota, ClientUsageMetrics


class RateLimitHeaderMixin:
    """
    Mixin to add standard rate limit headers to responses.
    
    Headers:
    - X-RateLimit-Limit: Maximum requests allowed in the window
    - X-RateLimit-Remaining: Requests remaining in current window
    - X-RateLimit-Reset: Unix timestamp when the window resets
    """
    
    def add_rate_limit_headers(self, request, limit, remaining, reset_time):
        """
        Add rate limit headers to the request for middleware to attach to response.
        """
        request.rate_limit_headers = {
            'X-RateLimit-Limit': str(limit),
            'X-RateLimit-Remaining': str(max(0, remaining)),
            'X-RateLimit-Reset': str(int(reset_time)),
        }


class GlobalAnonThrottle(AnonRateThrottle, RateLimitHeaderMixin):
    """
    Global rate limit for anonymous (unauthenticated) requests.
    
    Default: 100 requests per hour
    Configurable via: ANON_THROTTLE_RATE in settings
    """
    scope = 'anon'
    
    def allow_request(self, request, view):
        """Check if request is allowed and add rate limit headers."""
        # Get the throttle rate
        if not self.rate:
            return True
        
        # Check the throttle
        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True
        
        self.history = self.cache.get(self.key, [])
        self.now = self.timer()
        
        # Drop any requests from the history which have now passed the throttle duration
        while self.history and self.history[-1] <= self.now - self.duration:
            self.history.pop()
        
        if len(self.history) >= self.num_requests:
            # Calculate when the oldest request will expire
            reset_time = self.history[-1] + self.duration
            remaining = 0
            self.add_rate_limit_headers(request, self.num_requests, remaining, reset_time)
            return self.throttle_failure()
        
        # Allow the request
        remaining = self.num_requests - len(self.history) - 1
        reset_time = self.now + self.duration
        self.add_rate_limit_headers(request, self.num_requests, remaining, reset_time)
        return self.throttle_success()


class GlobalUserThrottle(UserRateThrottle, RateLimitHeaderMixin):
    """
    Global rate limit for authenticated users (without API key).
    
    Default: 1000 requests per hour
    Configurable via: USER_THROTTLE_RATE in settings
    """
    scope = 'user'
    
    def allow_request(self, request, view):
        """Check if request is allowed and add rate limit headers."""
        if not self.rate:
            return True
        
        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True
        
        self.history = self.cache.get(self.key, [])
        self.now = self.timer()
        
        while self.history and self.history[-1] <= self.now - self.duration:
            self.history.pop()
        
        if len(self.history) >= self.num_requests:
            reset_time = self.history[-1] + self.duration
            remaining = 0
            self.add_rate_limit_headers(request, self.num_requests, remaining, reset_time)
            return self.throttle_failure()
        
        remaining = self.num_requests - len(self.history) - 1
        reset_time = self.now + self.duration
        self.add_rate_limit_headers(request, self.num_requests, remaining, reset_time)
        return self.throttle_success()


class ClientQuotaThrottle(SimpleRateThrottle, RateLimitHeaderMixin):
    """
    Per-client rate limiting based on ClientQuota settings.
    
    Enforces quotas from ClientQuota model:
    - requests_per_minute
    - requests_per_hour
    - requests_per_day
    
    Uses Redis for persistent counters with automatic expiry.
    """
    
    scope = 'client_quota'
    
    def __init__(self):
        super().__init__()
        self.client = None
        self.quota = None
    
    def get_cache_key(self, request, view):
        """
        Generate cache key for the client.
        
        Returns None if no API client is found (no throttling applied).
        """
        # Get API client from request (set by authentication)
        self.client = getattr(request, 'api_client', None)
        if not self.client:
            return None
        
        # Get quota for client
        try:
            self.quota = ClientQuota.objects.get(client=self.client)
        except ClientQuota.DoesNotExist:
            # No quota defined, use default limits
            self.quota = None
            return None
        
        return f'throttle_client_{self.client.client_id}'
    
    def allow_request(self, request, view):
        """
        Check if request is allowed based on client quota.
        
        Checks three time windows:
        1. Requests per minute
        2. Requests per hour
        3. Requests per day
        
        Returns False (throttled) if ANY limit is exceeded.
        """
        if not self.quota:
            return True
        
        # Check each time window
        windows = [
            ('minute', 60, self.quota.requests_per_minute),
            ('hour', 3600, self.quota.requests_per_hour),
            ('day', 86400, self.quota.requests_per_day),
        ]
        
        self.now = time.time()
        
        for window_name, duration, limit in windows:
            if limit <= 0:  # Unlimited
                continue
            
            # Check this window
            allowed, remaining, reset_time = self._check_window(
                window_name, duration, limit
            )
            
            if not allowed:
                # Add headers for the exceeded limit
                self.add_rate_limit_headers(request, limit, 0, reset_time)
                
                # Record quota violation
                self._record_violation(window_name, limit)
                
                # Calculate wait time for Retry-After header
                wait = int(reset_time - self.now)
                raise Throttled(wait=wait, detail=f'{window_name.capitalize()} quota exceeded')
            
            # Add headers for the most restrictive limit
            if window_name == 'minute':
                self.add_rate_limit_headers(request, limit, remaining, reset_time)
        
        # All checks passed, record the request
        self._record_request()
        
        return True
    
    def _check_window(self, window_name, duration, limit):
        """
        Check if request is within limit for a specific time window.
        
        Returns: (allowed, remaining, reset_time)
        """
        cache_key = f'throttle_client_{self.client.client_id}_{window_name}'
        
        # Get current count from Redis
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            # Calculate reset time
            ttl = cache.ttl(cache_key)
            if ttl is None or ttl < 0:
                ttl = duration
            reset_time = self.now + ttl
            return False, 0, reset_time
        
        # Calculate remaining and reset time
        remaining = limit - current_count - 1
        reset_time = self.now + duration
        
        return True, remaining, reset_time
    
    def _record_request(self):
        """
        Record a successful request in all time windows.
        
        Increments counters in Redis with appropriate TTLs.
        """
        windows = [
            ('minute', 60),
            ('hour', 3600),
            ('day', 86400),
        ]
        
        for window_name, duration in windows:
            cache_key = f'throttle_client_{self.client.client_id}_{window_name}'
            
            # Increment counter
            try:
                cache.incr(cache_key)
            except ValueError:
                # Key doesn't exist, set it
                cache.set(cache_key, 1, timeout=duration)
    
    def _record_violation(self, window_name, limit):
        """
        Record a quota violation in ClientUsageMetrics.
        """
        try:
            metrics, created = ClientUsageMetrics.objects.get_or_create(
                client=self.client
            )
            metrics.quota_violations += 1
            metrics.save(update_fields=['quota_violations', 'last_activity'])
        except Exception:
            # Don't fail the request if metrics recording fails
            pass


class BurstRateThrottle(SimpleRateThrottle, RateLimitHeaderMixin):
    """
    Burst rate limiting for handling traffic spikes.
    
    Allows short bursts of traffic but enforces a sustained rate limit.
    
    Example: Allow 10 requests per second (burst) but only 100 per minute (sustained).
    
    Default: 20 requests per second
    Configurable via: BURST_THROTTLE_RATE in settings
    """
    scope = 'burst'
    
    def get_cache_key(self, request, view):
        """Generate cache key based on user or IP."""
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return f'throttle_burst_{self.scope}_{ident}'
    
    def allow_request(self, request, view):
        """Check burst rate limit."""
        if not self.rate:
            return True
        
        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True
        
        self.history = self.cache.get(self.key, [])
        self.now = self.timer()
        
        # Drop old requests from history
        while self.history and self.history[-1] <= self.now - self.duration:
            self.history.pop()
        
        if len(self.history) >= self.num_requests:
            reset_time = self.history[-1] + self.duration
            remaining = 0
            self.add_rate_limit_headers(request, self.num_requests, remaining, reset_time)
            
            wait = int(reset_time - self.now)
            raise Throttled(wait=wait, detail='Burst rate limit exceeded')
        
        remaining = self.num_requests - len(self.history) - 1
        reset_time = self.now + self.duration
        self.add_rate_limit_headers(request, self.num_requests, remaining, reset_time)
        return self.throttle_success()


class SustainedRateThrottle(SimpleRateThrottle, RateLimitHeaderMixin):
    """
    Sustained rate limiting to prevent continuous high traffic.
    
    Works in conjunction with BurstRateThrottle to allow bursts
    but prevent sustained abuse.
    
    Default: 1000 requests per hour
    Configurable via: SUSTAINED_THROTTLE_RATE in settings
    """
    scope = 'sustained'
    
    def get_cache_key(self, request, view):
        """Generate cache key based on user or IP."""
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return f'throttle_sustained_{self.scope}_{ident}'
    
    def allow_request(self, request, view):
        """Check sustained rate limit."""
        if not self.rate:
            return True
        
        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True
        
        self.history = self.cache.get(self.key, [])
        self.now = self.timer()
        
        while self.history and self.history[-1] <= self.now - self.duration:
            self.history.pop()
        
        if len(self.history) >= self.num_requests:
            reset_time = self.history[-1] + self.duration
            remaining = 0
            self.add_rate_limit_headers(request, self.num_requests, remaining, reset_time)
            
            wait = int(reset_time - self.now)
            raise Throttled(wait=wait, detail='Sustained rate limit exceeded')
        
        remaining = self.num_requests - len(self.history) - 1
        reset_time = self.now + self.duration
        self.add_rate_limit_headers(request, self.num_requests, remaining, reset_time)
        return self.throttle_success()
