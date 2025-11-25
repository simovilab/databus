# Security and Performance Hygiene - Issue #24

Complete implementation of security headers, CORS configuration, HTTP caching, pagination defaults, and connection timeouts for the Databús API.

## Overview

This implementation addresses four critical areas of API hygiene:

1. **CORS Configuration**: Cross-Origin Resource Sharing per environment
2. **HTTP Caching**: ETag, Last-Modified, and Cache-Control headers
3. **Pagination**: Sensible defaults and maximum caps
4. **Timeouts & Pooling**: Request timeouts and database connection pooling

## 1. CORS Configuration

### What is CORS?

CORS (Cross-Origin Resource Sharing) allows browsers to make requests from one domain to another. Without CORS configuration, browsers block cross-origin API requests for security.

### Implementation

**Package**: `django-cors-headers`

**Configuration** (in `settings.py`):

```python
# Allowed origins (per environment)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React dev server
    "http://localhost:8080",  # Vue dev server
    "https://databus.example.com",  # Production frontend
]

# Allow credentials (cookies, auth headers)
CORS_ALLOW_CREDENTIALS = True

# Allowed methods
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

# Allowed headers
CORS_ALLOW_HEADERS = [
    "authorization",
    "content-type",
    "x-api-key",  # Custom API key header
]

# Expose headers to browser JavaScript
CORS_EXPOSE_HEADERS = [
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-response-time",
    "etag",
]

# Cache preflight requests for 1 hour
CORS_PREFLIGHT_MAX_AGE = 3600
```

### Environment-Specific Configuration

**.env file**:

```bash
# Development (allow all origins)
CORS_ALLOW_ALL_ORIGINS=True
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080

# Production (strict whitelist)
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=https://app.databus.com,https://admin.databus.com
```

### Testing CORS

```bash
# Test preflight request
curl -X OPTIONS http://localhost:8000/api/feed/vehicles/ \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -v

# Expected response headers:
# Access-Control-Allow-Origin: http://localhost:3000
# Access-Control-Allow-Methods: GET, POST, ...
# Access-Control-Max-Age: 3600
```

## 2. HTTP Caching (ETag & Cache-Control)

### What is HTTP Caching?

HTTP caching reduces bandwidth and improves performance by:
- **ETag**: Identifies specific version of a resource
- **Last-Modified**: Timestamp of last modification
- **Cache-Control**: Directs caching behavior
- **304 Not Modified**: Skips sending unchanged content

### Implementation

**Middleware**: `api/cache_middleware.py` (5 classes)

#### ConditionalGetMiddleware

Handles ETag and Last-Modified headers for GET/HEAD requests.

```python
# Request 1 (no cache)
GET /api/gtfs/agencies/
→ 200 OK (full response)
ETag: "abc123"
Cache-Control: max-age=3600

# Request 2 (with cache)
GET /api/gtfs/agencies/
If-None-Match: "abc123"
→ 304 Not Modified (no body, saves bandwidth)
```

#### APICacheControlMiddleware

Sets Cache-Control headers based on endpoint type:

| Endpoint | Cache Time | Reason |
|----------|-----------|---------|
| `/api/gtfs/*` | 1 hour | Static schedule data |
| `/api/feed/*` | 30 seconds | Realtime vehicle positions |
| `/api/` (root) | 1 hour | API metadata |
| POST/PUT/DELETE | No cache | Write operations |

#### LastModifiedMiddleware

Adds Last-Modified header from model timestamps:

```python
class VehicleViewSet(viewsets.ModelViewSet):
    def get_last_modified(self):
        """Return timestamp of most recent update."""
        return Vehicle.objects.latest('updated_at').updated_at
```

#### SecurityHeadersMiddleware

Adds security headers to all responses:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'
```

#### APIResponseTimingMiddleware

Adds `X-Response-Time` header for monitoring:

```
X-Response-Time: 145ms
```

### Cache Configuration

**In settings.py**:

```python
CACHE_TTL = {
    "gtfs_static": 3600,      # 1 hour
    "realtime_feed": 30,      # 30 seconds
    "api_response": 300,      # 5 minutes
    "user_session": 1800,     # 30 minutes
}
```

### Testing Caching

```bash
# First request (cache miss)
curl -i http://localhost:8000/api/gtfs/agencies/
# → 200 OK
# ETag: "abc123"
# Cache-Control: public, max-age=3600

# Second request (cache hit)
curl -i -H "If-None-Match: abc123" http://localhost:8000/api/gtfs/agencies/
# → 304 Not Modified
# (No body, bandwidth saved)
```

### Vary Header

The `Vary` header ensures proper cache keying:

```
Vary: Accept, Accept-Encoding, Authorization
```

This tells caches to store separate versions for:
- Different content types (`Accept`)
- Different compressions (`Accept-Encoding`)
- Different users (`Authorization`)

## 3. Pagination Defaults and Max Caps

### Why Pagination Matters

Without pagination limits:
- Clients can request millions of records
- Database queries become slow
- Memory usage explodes
- API becomes unresponsive

### Implementation

**File**: `api/pagination.py` (9 pagination classes)

#### StandardPageNumberPagination

Default pagination for most endpoints:

```python
page_size = 50
max_page_size = 100
```

**Usage**:
```bash
GET /api/gtfs/stops/?page=1&page_size=25
```

**Response**:
```json
{
  "count": 1500,
  "next": "http://api/gtfs/stops/?page=2",
  "previous": null,
  "page_size": 25,
  "total_pages": 60,
  "current_page": 1,
  "results": [...]
}
```

#### Pagination Class Summary

| Class | Default | Max | Use Case |
|-------|---------|-----|----------|
| `StandardPageNumberPagination` | 50 | 100 | Most endpoints |
| `SmallResultSetPagination` | 25 | 50 | Agencies, operators |
| `LargeResultSetPagination` | 100 | 500 | Stop times, shapes |
| `RealtimeFeedPagination` | 50 | 200 | Vehicle positions |
| `VehiclePositionCursorPagination` | 50 | 200 | Cursor-based for efficiency |
| `AuditLogCursorPagination` | 100 | 500 | Large audit logs |

#### Using Custom Pagination

**In viewsets**:

```python
from api.pagination import LargeResultSetPagination

class StopTimeViewSet(viewsets.ModelViewSet):
    queryset = StopTime.objects.all()
    pagination_class = LargeResultSetPagination
```

**Or use helper**:

```python
from api.pagination import get_pagination_class

class VehicleViewSet(viewsets.ModelViewSet):
    pagination_class = get_pagination_class('realtime')
```

#### Cursor Pagination

For large datasets with frequent updates, use cursor pagination:

**Advantages**:
- More efficient than offset pagination
- Consistent results even when data changes
- No limit on total pages

**Example**:

```bash
GET /api/feed/vehicles/?cursor=cD0yMDI1LTEx
```

**Response**:
```json
{
  "next": "http://api/feed/vehicles/?cursor=cj0xNQ==",
  "previous": "http://api/feed/vehicles/?cursor=cj05",
  "results": [...]
}
```

### Preventing Abuse

All pagination classes enforce max limits:

```python
# User requests excessive page size
GET /api/gtfs/stops/?page_size=10000

# Server responds with max allowed
{
  "page_size": 100,  # Capped at max_page_size
  "results": [...]   # Only 100 items
}
```

## 4. Request Timeouts and Connection Pooling

### Database Connection Pooling

**Problem**: Creating new database connections is expensive (50-100ms per connection).

**Solution**: Reuse connections via pooling.

**Configuration** (in `settings.py`):

```python
# Persistent connections
CONN_MAX_AGE = 600  # Keep connections alive for 10 minutes

# Connection timeout
DATABASE_CONNECT_TIMEOUT = 5  # Fail fast if DB unreachable

# Statement timeout (PostgreSQL)
DATABASE_STATEMENT_TIMEOUT = 30000  # Kill queries after 30 seconds

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'CONN_MAX_AGE': CONN_MAX_AGE,
        'OPTIONS': {
            'connect_timeout': DATABASE_CONNECT_TIMEOUT,
            'options': f'-c statement_timeout={DATABASE_STATEMENT_TIMEOUT}',
        },
    }
}
```

**Benefits**:
- 5-10x faster request handling
- Reduced database load
- Better resource utilization

### Redis Connection Pooling

**Already configured** (from previous issues):

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
        'OPTIONS': {
            'db': '1',
            'pool_class': 'redis.BlockingConnectionPool',
        },
    }
}
```

**Pool settings**:
- Max connections: 50 (default)
- Connection timeout: 20 seconds
- Blocking on pool exhaustion

### HTTP Request Timeouts

For external API calls (GTFS feeds, webhooks, etc.):

```python
# In settings.py
REQUEST_TIMEOUT = 30  # Total request timeout
REQUEST_CONNECT_TIMEOUT = 5  # Connection timeout

# Usage in code
import requests

response = requests.get(
    'https://api.example.com/gtfs',
    timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_TIMEOUT)
)
```

### Celery Task Timeouts

For background tasks:

```python
# In settings.py
CELERY_TASK_TIME_LIMIT = 300  # Hard limit (5 minutes)
CELERY_TASK_SOFT_TIME_LIMIT = 240  # Soft limit (4 minutes)

# In tasks
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

@shared_task
def process_gtfs_feed():
    try:
        # Process data
        pass
    except SoftTimeLimitExceeded:
        # Cleanup and exit gracefully
        logger.warning('Task soft timeout reached')
```

### Monitoring Connection Pool

```bash
# PostgreSQL: Check active connections
docker-compose exec db psql -U postgres -d realtime -c "
SELECT count(*) as connections,
       state,
       wait_event_type
FROM pg_stat_activity
WHERE datname = 'realtime'
GROUP BY state, wait_event_type;
"

# Redis: Check connected clients
docker-compose exec redis redis-cli CLIENT LIST
```

## Environment Configuration

### Development (.env)

```bash
# Relaxed settings for development
DEBUG=True
CORS_ALLOW_ALL_ORIGINS=True
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False

# Shorter timeouts for faster feedback
CONN_MAX_AGE=60
DATABASE_STATEMENT_TIMEOUT=10000
REQUEST_TIMEOUT=10
```

### Staging (.env)

```bash
# Production-like settings with debugging
DEBUG=False
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=https://staging.databus.com
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Production-like timeouts
CONN_MAX_AGE=600
DATABASE_STATEMENT_TIMEOUT=30000
REQUEST_TIMEOUT=30
```

### Production (.env)

```bash
# Strict security settings
DEBUG=False
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=https://databus.com,https://api.databus.com
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Longer connection pooling
CONN_MAX_AGE=600
DATABASE_STATEMENT_TIMEOUT=30000
REQUEST_TIMEOUT=30
CELERY_TASK_TIME_LIMIT=300
```

## Security Headers Reference

All API responses include these security headers:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Enable XSS filter (legacy) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer info |
| `Content-Security-Policy` | `default-src 'self'` | Restrict resource loading |
| `Strict-Transport-Security` | `max-age=31536000` | Force HTTPS (production) |

## Performance Monitoring

### Response Time Header

Every response includes timing:

```bash
curl -i http://localhost:8000/api/gtfs/agencies/
# X-Response-Time: 45ms
```

### Cache Hit Monitoring

```bash
# Check cache hit rate
docker-compose exec redis redis-cli INFO stats | grep keyspace

# Monitor cache keys
docker-compose exec redis redis-cli --scan --pattern "cache:*" | head -20
```

### Database Query Performance

```bash
# Enable query logging in development
# settings.py
LOGGING = {
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
}
```

## Testing

### Test CORS

```bash
# Allowed origin
curl -X GET http://localhost:8000/api/ \
  -H "Origin: http://localhost:3000" \
  -v | grep "Access-Control"

# Disallowed origin (should be blocked in production)
curl -X GET http://localhost:8000/api/ \
  -H "Origin: http://evil.com" \
  -v | grep "Access-Control"
```

### Test Caching

```bash
# First request (cache miss)
curl -i http://localhost:8000/api/gtfs/agencies/ \
  | grep -E "(ETag|Cache-Control)"

# Extract ETag
ETAG=$(curl -si http://localhost:8000/api/gtfs/agencies/ \
  | grep ETag | cut -d' ' -f2)

# Second request (cache hit)
curl -i -H "If-None-Match: $ETAG" \
  http://localhost:8000/api/gtfs/agencies/
# → Should return 304 Not Modified
```

### Test Pagination

```bash
# Test default pagination
curl "http://localhost:8000/api/gtfs/stops/" | jq '.page_size'
# → 50

# Test custom page size
curl "http://localhost:8000/api/gtfs/stops/?page_size=25" | jq '.page_size'
# → 25

# Test max cap
curl "http://localhost:8000/api/gtfs/stops/?page_size=10000" | jq '.page_size'
# → 100 (capped at max_page_size)
```

### Test Timeouts

```bash
# Database timeout test
docker-compose exec web python manage.py shell -c "
from django.db import connection
import time

# Should timeout after 30 seconds
cursor = connection.cursor()
try:
    cursor.execute('SELECT pg_sleep(60)')
except Exception as e:
    print(f'Timeout caught: {e}')
"
```

## Troubleshooting

### CORS Issues

**Problem**: Browser blocks API requests

**Solution**: Check CORS configuration

```bash
# Verify CORS middleware is enabled
docker-compose exec web python manage.py diffsettings | grep MIDDLEWARE

# Check CORS settings
docker-compose exec web python manage.py shell -c "
from django.conf import settings
print('CORS_ALLOWED_ORIGINS:', settings.CORS_ALLOWED_ORIGINS)
print('CORS_ALLOW_ALL_ORIGINS:', settings.CORS_ALLOW_ALL_ORIGINS)
"
```

### Cache Not Working

**Problem**: ETag headers not appearing

**Solution**: Check middleware order

```bash
# Verify cache middleware is enabled
docker-compose exec web python manage.py diffsettings | grep cache_middleware

# Test manually
curl -i http://localhost:8000/api/gtfs/agencies/ | grep ETag
```

### Pagination Too Slow

**Problem**: Large page sizes causing timeouts

**Solution**: Use cursor pagination for large datasets

```python
from api.pagination import VehiclePositionCursorPagination

class VehicleViewSet(viewsets.ModelViewSet):
    pagination_class = VehiclePositionCursorPagination
```

### Connection Pool Exhausted

**Problem**: "Too many connections" error

**Solution**: Reduce `CONN_MAX_AGE` or increase PostgreSQL `max_connections`

```bash
# Check current connections
docker-compose exec db psql -U postgres -c "SHOW max_connections;"

# Increase if needed (in postgresql.conf)
max_connections = 200
```

## Performance Benchmarks

Expected performance improvements:

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Response time (cached) | 150ms | 2ms | 75x faster |
| Bandwidth (cached) | 50KB | 0.3KB | 167x less |
| Database connections | 1 per request | Pooled | 5-10x faster |
| Max pagination | Unlimited | 100-500 | Prevents abuse |

## Best Practices

### 1. CORS

- ✅ Use specific origin whitelist in production
- ✅ Enable credentials only if needed
- ✅ Expose only necessary headers
- ❌ Don't use `CORS_ALLOW_ALL_ORIGINS=True` in production

### 2. Caching

- ✅ Cache static data (GTFS schedules)
- ✅ Short cache for realtime data (vehicles)
- ✅ Use ETag for conditional requests
- ❌ Don't cache user-specific data
- ❌ Don't cache write operations

### 3. Pagination

- ✅ Always set a default page size
- ✅ Always enforce a max page size
- ✅ Use cursor pagination for large datasets
- ❌ Don't allow unlimited page sizes
- ❌ Don't use offset pagination for millions of rows

### 4. Timeouts

- ✅ Set timeouts for all external requests
- ✅ Use connection pooling
- ✅ Monitor connection usage
- ❌ Don't use infinite timeouts
- ❌ Don't create connections per request

## References

- CORS: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
- HTTP Caching: https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching
- ETag: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag
- DRF Pagination: https://www.django-rest-framework.org/api-guide/pagination/
- PostgreSQL Connection Pooling: https://www.postgresql.org/docs/current/runtime-config-connection.html
- Django CORS Headers: https://github.com/adamchainz/django-cors-headers

## Acceptance Criteria Status

| Criterion | Status |
|-----------|--------|
| ✅ CORS config per environment | **COMPLETE** |
| ✅ ETag/Last-Modified and cache headers where safe | **COMPLETE** |
| ✅ Sensible pagination defaults and max caps | **COMPLETE** |
| ✅ Request timeouts and connection pooling | **COMPLETE** |

**Issue #24: Security and performance hygiene** - ✅ **COMPLETE**
