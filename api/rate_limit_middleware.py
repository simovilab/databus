"""
Middleware for automatic rate limit header injection and usage tracking.

Adds rate limit headers to all API responses and tracks usage metrics
for API clients.
"""

import time
from django.utils.deprecation import MiddlewareMixin
from api.client_models import APIClient, ClientUsageMetrics


class RateLimitHeaderMiddleware(MiddlewareMixin):
    """
    Middleware to add rate limit headers to all responses.
    
    Headers are set by throttle classes and attached to the request
    object. This middleware transfers them to the response.
    
    Headers:
    - X-RateLimit-Limit: Maximum requests allowed
    - X-RateLimit-Remaining: Requests remaining in current window
    - X-RateLimit-Reset: Unix timestamp when limit resets
    - Retry-After: (only on 429) Seconds until retry is allowed
    """
    
    def process_response(self, request, response):
        """Add rate limit headers to response if they were set by throttling."""
        # Check if throttle classes set headers on the request
        if hasattr(request, 'rate_limit_headers'):
            for header, value in request.rate_limit_headers.items():
                response[header] = value
        
        # For 429 responses, ensure Retry-After header is present
        if response.status_code == 429:
            if 'Retry-After' not in response:
                # Default to 60 seconds if not set
                response['Retry-After'] = '60'
        
        return response


class ClientUsageTrackingMiddleware(MiddlewareMixin):
    """
    Middleware to automatically track API usage metrics for clients.
    
    Updates ClientUsageMetrics for each request:
    - Increments request counters
    - Tracks response times
    - Records data transfer (request/response sizes)
    - Updates last activity timestamp
    - Records error rates
    """
    
    def process_request(self, request):
        """Record request start time."""
        request._usage_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Track usage metrics for the request."""
        # Only track if an API client is present
        client = getattr(request, 'api_client', None)
        if not client:
            return response
        
        # Calculate response time
        if hasattr(request, '_usage_start_time'):
            response_time_ms = int((time.time() - request._usage_start_time) * 1000)
        else:
            response_time_ms = 0
        
        # Get or create metrics
        try:
            metrics, created = ClientUsageMetrics.objects.get_or_create(
                client=client
            )
            
            # Update counters
            metrics.total_requests += 1
            
            # Track success/error
            if 200 <= response.status_code < 400:
                metrics.successful_requests += 1
            else:
                metrics.failed_requests += 1
            
            # Track response time
            if response_time_ms > 0:
                # Update average response time (incremental average)
                if metrics.average_response_time_ms == 0:
                    metrics.average_response_time_ms = response_time_ms
                else:
                    # Weighted average (last 1000 requests)
                    weight = min(metrics.total_requests, 1000)
                    metrics.average_response_time_ms = int(
                        (metrics.average_response_time_ms * (weight - 1) + response_time_ms) / weight
                    )
            
            # Track data transfer
            try:
                # Request size (approximate from headers)
                request_size = len(request.body) if hasattr(request, 'body') else 0
                metrics.data_in_bytes += request_size
                
                # Response size
                if hasattr(response, 'content'):
                    response_size = len(response.content)
                    metrics.data_out_bytes += response_size
            except Exception:
                # Don't fail if we can't calculate sizes
                pass
            
            # Track specific response codes
            if response.status_code == 429:
                metrics.quota_violations += 1
            
            # Update last activity
            metrics.save()
            
        except Exception as e:
            # Don't fail the request if metrics tracking fails
            # But log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f'Failed to track usage metrics for client {client.client_id}: {e}')
        
        return response
    
    def process_exception(self, request, exception):
        """Track exceptions in metrics."""
        client = getattr(request, 'api_client', None)
        if not client:
            return None
        
        try:
            metrics, created = ClientUsageMetrics.objects.get_or_create(
                client=client
            )
            metrics.total_requests += 1
            metrics.failed_requests += 1
            metrics.save()
        except Exception:
            pass
        
        return None


class APIClientAuthMiddleware(MiddlewareMixin):
    """
    Middleware to authenticate API clients using API keys.
    
    Checks for API key in:
    1. Authorization header: "Authorization: ApiKey key_xxxx..."
    2. X-API-Key header: "X-API-Key: key_xxxx..."
    3. Query parameter: "?api_key=key_xxxx..."
    
    If valid API key is found, attaches APIClient to request as request.api_client.
    """
    
    def process_request(self, request):
        """Extract and validate API key from request."""
        api_key = self._extract_api_key(request)
        
        if not api_key:
            return None
        
        # Validate API key
        from api.client_models import APIKey
        
        try:
            # Find valid API key
            api_key_obj = APIKey.objects.select_related('client').filter(
                key_prefix=api_key[:12],  # Use prefix for faster lookup
                is_active=True
            ).first()
            
            if api_key_obj and api_key_obj.is_valid() and api_key_obj.verify_key(api_key):
                # Attach client to request
                request.api_client = api_key_obj.client
                request.api_key = api_key_obj
                
                # Update last used timestamp
                api_key_obj.update_last_used()
                
        except Exception as e:
            # Don't fail request if validation fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f'API key validation failed: {e}')
        
        return None
    
    def _extract_api_key(self, request):
        """
        Extract API key from various sources.
        
        Priority:
        1. Authorization header (standard)
        2. X-API-Key header (common alternative)
        3. Query parameter (least secure, use with caution)
        """
        # Check Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('ApiKey '):
            return auth_header[7:]  # Remove "ApiKey " prefix
        
        # Check X-API-Key header
        api_key_header = request.META.get('HTTP_X_API_KEY', '')
        if api_key_header:
            return api_key_header
        
        # Check query parameter (least preferred)
        api_key_param = request.GET.get('api_key', '')
        if api_key_param:
            return api_key_param
        
        return None
