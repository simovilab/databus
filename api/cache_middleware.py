"""
HTTP Caching and ETag middleware for Databús API.

Implements:
- ETag generation for GET/HEAD requests
- Last-Modified headers
- Cache-Control headers
- Conditional requests (304 Not Modified)
- Vary headers for proper cache keying
"""

import hashlib
import time
from django.utils.cache import (
    get_conditional_response,
    set_response_etag,
    patch_cache_control,
)
from django.utils.http import http_date, parse_http_date_safe
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache


class ConditionalGetMiddleware(MiddlewareMixin):
    """
    Middleware to handle conditional GET requests with ETag and Last-Modified.
    
    For GET/HEAD requests to API endpoints:
    1. Generates ETag based on response content
    2. Checks If-None-Match header (ETag comparison)
    3. Checks If-Modified-Since header (timestamp comparison)
    4. Returns 304 Not Modified if content hasn't changed
    
    This reduces bandwidth and improves performance for repeated requests.
    """
    
    def process_response(self, request, response):
        """Process response to add caching headers and handle conditional requests."""
        # Only process successful GET/HEAD requests
        if request.method not in ('GET', 'HEAD'):
            return response
        
        if response.status_code != 200:
            return response
        
        # Skip if response explicitly disables caching
        if response.get('Cache-Control', '').startswith('no-cache'):
            return response
        
        # Set ETag based on content
        if not response.has_header('ETag'):
            set_response_etag(response)
        
        # Check for conditional request and return 304 if appropriate
        etag = response.get('ETag')
        last_modified = response.get('Last-Modified')
        
        if etag or last_modified:
            conditional_response = get_conditional_response(
                request,
                etag=etag,
                last_modified=last_modified,
                response=response,
            )
            if conditional_response:
                return conditional_response
        
        return response


class APICacheControlMiddleware(MiddlewareMixin):
    """
    Middleware to set appropriate Cache-Control headers for API responses.
    
    Applies different caching strategies based on endpoint type:
    - Static data (GTFS): Long cache times (1 hour)
    - Realtime data: Short cache times (30 seconds)
    - User-specific data: No cache
    - Write operations: No cache
    """
    
    # Cache times in seconds
    CACHE_TIMES = {
        'gtfs': 3600,        # GTFS data: 1 hour
        'realtime': 30,      # Realtime feeds: 30 seconds
        'static': 86400,     # Static assets: 24 hours
        'api_root': 3600,    # API root: 1 hour
    }
    
    def process_response(self, request, response):
        """Set Cache-Control headers based on endpoint and response."""
        # Only process successful GET/HEAD requests
        if request.method not in ('GET', 'HEAD'):
            # Write operations should never be cached
            patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
            return response
        
        if response.status_code != 200:
            return response
        
        # Skip if Cache-Control already set
        if response.has_header('Cache-Control'):
            return response
        
        # Determine cache time based on path
        path = request.path
        cache_time = self._get_cache_time(path)
        
        if cache_time > 0:
            # Set caching headers
            patch_cache_control(
                response,
                public=True,
                max_age=cache_time,
                s_maxage=cache_time,  # Shared cache (CDN)
            )
            
            # Add Vary header for proper cache keying
            vary_headers = ['Accept', 'Accept-Encoding']
            
            # Add Authorization to Vary if user-specific
            if hasattr(request, 'user') and request.user.is_authenticated:
                vary_headers.append('Authorization')
            
            if hasattr(request, 'api_client') and request.api_client:
                vary_headers.append('Authorization')
            
            existing_vary = response.get('Vary', '')
            if existing_vary:
                vary_headers.append(existing_vary)
            
            response['Vary'] = ', '.join(vary_headers)
        else:
            # No caching
            patch_cache_control(response, no_cache=True, must_revalidate=True)
        
        return response
    
    def _get_cache_time(self, path):
        """Determine appropriate cache time based on path."""
        if '/api/gtfs/' in path:
            return self.CACHE_TIMES['gtfs']
        elif '/api/feed/' in path:
            return self.CACHE_TIMES['realtime']
        elif path == '/api/' or path == '/api':
            return self.CACHE_TIMES['api_root']
        elif '/static/' in path or '/media/' in path:
            return self.CACHE_TIMES['static']
        else:
            # Default: short cache for other API endpoints
            return 300  # 5 minutes


class LastModifiedMiddleware(MiddlewareMixin):
    """
    Middleware to add Last-Modified headers based on model timestamps.
    
    For resources with 'updated_at' or 'modified_at' fields, this middleware
    automatically adds the Last-Modified header to enable conditional requests.
    """
    
    def process_response(self, request, response):
        """Add Last-Modified header if available."""
        # Only for successful GET/HEAD requests
        if request.method not in ('GET', 'HEAD'):
            return response
        
        if response.status_code != 200:
            return response
        
        # Skip if Last-Modified already set
        if response.has_header('Last-Modified'):
            return response
        
        # Try to get timestamp from view
        view = getattr(request, 'view', None)
        if not view:
            return response
        
        # Check if view has last_modified method
        if hasattr(view, 'get_last_modified'):
            try:
                last_modified = view.get_last_modified()
                if last_modified:
                    response['Last-Modified'] = http_date(last_modified.timestamp())
            except Exception:
                pass
        
        return response


class CompressionVaryMiddleware(MiddlewareMixin):
    """
    Middleware to ensure Vary header includes Accept-Encoding for compressed responses.
    
    This is important for proper caching when GZip/Brotli compression is enabled.
    """
    
    def process_response(self, request, response):
        """Ensure Accept-Encoding is in Vary header."""
        if response.status_code == 200 and request.method in ('GET', 'HEAD'):
            vary = response.get('Vary', '')
            if 'Accept-Encoding' not in vary:
                if vary:
                    response['Vary'] = f"{vary}, Accept-Encoding"
                else:
                    response['Vary'] = 'Accept-Encoding'
        
        return response


class APIResponseTimingMiddleware(MiddlewareMixin):
    """
    Middleware to add response timing headers for monitoring and debugging.
    
    Adds X-Response-Time header with processing time in milliseconds.
    """
    
    def process_request(self, request):
        """Record request start time."""
        request._api_start_time = time.time()
    
    def process_response(self, request, response):
        """Add timing header."""
        if hasattr(request, '_api_start_time'):
            duration_ms = int((time.time() - request._api_start_time) * 1000)
            response['X-Response-Time'] = f"{duration_ms}ms"
        
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers to all responses.
    
    Headers:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Content-Security-Policy: default-src 'self'
    """
    
    def process_response(self, request, response):
        """Add security headers."""
        # Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Prevent clickjacking
        if not response.has_header('X-Frame-Options'):
            response['X-Frame-Options'] = 'DENY'
        
        # XSS protection (for older browsers)
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer policy
        if not response.has_header('Referrer-Policy'):
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy for API responses
        if request.path.startswith('/api/') and not response.has_header('Content-Security-Policy'):
            response['Content-Security-Policy'] = "default-src 'self'"
        
        return response
