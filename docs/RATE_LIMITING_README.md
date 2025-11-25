# Rate Limiting and Quota Management

Complete rate limiting and quota system for Databús API (Issue #23).

## Overview

The rate limiting system protects the API from abuse and ensures fair resource allocation across clients. It implements multiple layers of protection:

1. **Global Rate Limits**: Basic protection for anonymous and authenticated users
2. **Per-Client Quotas**: Customizable limits based on `ClientQuota` model
3. **Burst Protection**: Prevents rapid-fire requests
4. **Sustained Limits**: Prevents continuous high traffic
5. **Usage Tracking**: Automatic metrics collection in `ClientUsageMetrics`

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                      HTTP Request                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           APIClientAuthMiddleware                            │
│  - Extracts API key from headers/params                      │
│  - Validates key and attaches api_client to request          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Throttle Classes (DRF)                          │
│  1. GlobalAnonThrottle (100/hour)                            │
│  2. GlobalUserThrottle (1000/hour)                           │
│  3. ClientQuotaThrottle (per-client, from DB)                │
│  4. BurstRateThrottle (20/second)                            │
│  5. SustainedRateThrottle (1000/hour)                        │
│                                                               │
│  Counters stored in Redis with automatic expiry              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                 ┌─────┴─────┐
                 │           │
          Allowed│           │Throttled (429)
                 ▼           ▼
┌────────────────────┐  ┌──────────────────────┐
│   View Handler     │  │   429 Response       │
│                    │  │  + Retry-After       │
└────────┬───────────┘  └──────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│        RateLimitHeaderMiddleware                             │
│  Adds headers to response:                                   │
│  - X-RateLimit-Limit: Maximum requests                       │
│  - X-RateLimit-Remaining: Requests left                      │
│  - X-RateLimit-Reset: Unix timestamp of reset                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│       ClientUsageTrackingMiddleware                          │
│  Records metrics in ClientUsageMetrics:                      │
│  - Total/successful/failed requests                          │
│  - Response times                                            │
│  - Data transfer                                             │
│  - Quota violations                                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
                  HTTP Response
```

## Rate Limit Tiers

### 1. Anonymous Users (No Authentication)

- **Limit**: 100 requests/hour
- **Scope**: `anon`
- **Throttle Class**: `GlobalAnonThrottle`
- **Key**: Client IP address

```bash
# Example request
curl http://localhost:8000/api/gtfs/agencies/

# Response headers
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1732578000
```

### 2. Authenticated Users (JWT/Session, No API Key)

- **Limit**: 1000 requests/hour
- **Scope**: `user`
- **Throttle Class**: `GlobalUserThrottle`
- **Key**: User ID

```bash
# Example request
curl -H "Authorization: Bearer <jwt_token>" \
     http://localhost:8000/api/gtfs/agencies/

# Response headers
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1732578000
```

### 3. API Clients (With API Key)

- **Limit**: Defined in `ClientQuota` model per client
- **Scope**: `client_quota`
- **Throttle Class**: `ClientQuotaThrottle`
- **Key**: Client ID
- **Windows**: Per minute, per hour, per day

```bash
# Example request
curl -H "Authorization: ApiKey key_abc123..." \
     http://localhost:8000/api/gtfs/agencies/

# Response headers (from minute quota)
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1732574660
```

**Default Quotas** (in `ClientQuota` model):
- **requests_per_minute**: 60 (1 req/second average)
- **requests_per_hour**: 1000
- **requests_per_day**: 10000

### 4. Burst Protection

- **Limit**: 20 requests/second
- **Scope**: `burst`
- **Throttle Class**: `BurstRateThrottle`
- **Purpose**: Prevent rapid-fire attacks

Allows short bursts of traffic but prevents sustained rapid requests.

### 5. Sustained Rate Limit

- **Limit**: 1000 requests/hour
- **Scope**: `sustained`
- **Throttle Class**: `SustainedRateThrottle`
- **Purpose**: Prevent continuous high traffic

Works with burst protection: allows short spikes but enforces long-term limits.

## API Key Authentication

### Methods to Provide API Key

The system accepts API keys in three ways (in priority order):

#### 1. Authorization Header (Recommended)

```bash
curl -H "Authorization: ApiKey key_abc123xyz..." \
     http://localhost:8000/api/feed/vehicles/
```

#### 2. X-API-Key Header

```bash
curl -H "X-API-Key: key_abc123xyz..." \
     http://localhost:8000/api/feed/vehicles/
```

#### 3. Query Parameter (Least Secure)

```bash
curl "http://localhost:8000/api/feed/vehicles/?api_key=key_abc123xyz..."
```

⚠️ **Security Note**: Query parameters are logged in server logs and browser history. Use headers for production.

## Client Quota Management

### Setting Custom Quotas

Quotas are defined per-client in the `ClientQuota` model:

```python
from api.client_models import APIClient, ClientQuota

# Get client
client = APIClient.objects.get(client_id='client_abc123...')

# Create/update quota
quota, created = ClientQuota.objects.update_or_create(
    client=client,
    defaults={
        'requests_per_minute': 120,  # 2 req/second
        'requests_per_hour': 5000,
        'requests_per_day': 50000,
        'max_data_points_per_request': 1000,
        'feature_permissions': {
            'realtime_feed': True,
            'historical_data': True,
            'predictions': False
        }
    }
)
```

### Unlimited Quotas

Set any limit to `0` or negative value for unlimited:

```python
quota.requests_per_minute = 0  # Unlimited per minute
quota.requests_per_hour = -1   # Unlimited per hour
quota.save()
```

⚠️ **Note**: Use unlimited quotas carefully. Burst and sustained limits still apply.

### Via Django Admin

1. Navigate to `/admin/api/clientquota/`
2. Select client
3. Edit quota values
4. Save (automatically logs changes in audit trail)

## Response Headers

### Success Responses (200-399)

All successful responses include rate limit headers:

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1732574700
Content-Type: application/json
```

**Header Definitions**:
- `X-RateLimit-Limit`: Maximum requests allowed in current window
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Reset`: Unix timestamp when the limit resets

### Throttled Responses (429)

When rate limit is exceeded:

```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1732574700
Retry-After: 45
Content-Type: application/json

{
  "detail": "Minute quota exceeded"
}
```

**Additional Header**:
- `Retry-After`: Seconds to wait before retrying

## Counter Persistence

### Redis Storage

All rate limit counters are stored in Redis with automatic expiry:

```
Key Format: throttle_{scope}_{identifier}_{window}
Examples:
  throttle_client_client_abc123_minute
  throttle_client_client_abc123_hour
  throttle_client_client_abc123_day
  throttle_anon_192.168.1.100_hour
  throttle_user_42_hour
```

### Automatic Expiry

Counters automatically expire after their time window:
- **Minute counters**: TTL = 60 seconds
- **Hour counters**: TTL = 3600 seconds
- **Day counters**: TTL = 86400 seconds

### Reset Policy

Counters use **sliding windows**:
- Old requests are dropped from history as they age out
- No hard resets at fixed times
- Smoother rate limiting behavior

## Usage Metrics Tracking

### Automatic Collection

The `ClientUsageTrackingMiddleware` automatically records metrics for every API request:

```python
class ClientUsageMetrics(models.Model):
    client = models.OneToOneField(APIClient)
    
    # Request counters
    total_requests = models.BigIntegerField(default=0)
    successful_requests = models.BigIntegerField(default=0)
    failed_requests = models.BigIntegerField(default=0)
    quota_violations = models.BigIntegerField(default=0)
    
    # Performance metrics
    average_response_time_ms = models.IntegerField(default=0)
    
    # Data transfer
    data_in_bytes = models.BigIntegerField(default=0)
    data_out_bytes = models.BigIntegerField(default=0)
    
    # Timestamps
    last_activity = models.DateTimeField(auto_now=True)
```

### Viewing Metrics

#### Via API

```bash
# Get metrics for your client
curl -H "Authorization: ApiKey key_abc123..." \
     http://localhost:8000/api/clients/{client_id}/metrics/

# Response
{
  "client": "client_abc123...",
  "total_requests": 15234,
  "successful_requests": 15100,
  "failed_requests": 134,
  "quota_violations": 12,
  "success_rate": 99.12,
  "violation_rate": 0.08,
  "average_response_time_ms": 145,
  "total_data_in_mb": 45.2,
  "total_data_out_mb": 892.5,
  "last_activity": "2025-11-25T10:30:45Z"
}
```

#### Via Django Admin

Navigate to `/admin/api/clientusagemetrics/` to view all metrics.

## Configuration

### Global Settings

In `realtime/settings.py`:

```python
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'api.throttling.GlobalAnonThrottle',
        'api.throttling.GlobalUserThrottle',
        'api.throttling.ClientQuotaThrottle',
        'api.throttling.BurstRateThrottle',
        'api.throttling.SustainedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'client_quota': None,  # Managed per-client
        'burst': '20/second',
        'sustained': '1000/hour',
    },
}
```

### Per-View Overrides

Override throttling for specific views:

```python
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import UserRateThrottle

@api_view(['GET'])
@throttle_classes([UserRateThrottle])
def expensive_operation(request):
    """This view uses only user throttling."""
    pass
```

Or in ViewSets:

```python
from rest_framework import viewsets
from api.throttling import ClientQuotaThrottle

class VehicleViewSet(viewsets.ModelViewSet):
    throttle_classes = [ClientQuotaThrottle]  # Only client quota
```

### Disable Throttling

For specific views (use with caution):

```python
from rest_framework.decorators import api_view, throttle_classes

@api_view(['GET'])
@throttle_classes([])  # No throttling
def internal_endpoint(request):
    """This view has no rate limits."""
    pass
```

## Testing

### Running Tests

```bash
# Run all rate limiting tests
docker-compose exec web python manage.py test api.test_rate_limiting

# Run specific test class
docker-compose exec web python manage.py test api.test_rate_limiting.ClientQuotaThrottleTest

# Run with verbose output
docker-compose exec web python manage.py test api.test_rate_limiting -v 2
```

### Test Coverage

The test suite includes:
- ✅ Global anonymous limits
- ✅ Global authenticated user limits
- ✅ Per-client quota limits (minute/hour/day)
- ✅ Burst traffic handling
- ✅ Sustained rate limits
- ✅ Rate limit headers (all responses)
- ✅ 429 responses with Retry-After
- ✅ Counter persistence in Redis
- ✅ Counter expiry and reset
- ✅ Usage metrics tracking
- ✅ Quota violation recording
- ✅ Integration tests

## Client Examples

### Python

```python
import requests
import time

API_KEY = 'key_abc123...'
BASE_URL = 'http://localhost:8000/api'

headers = {
    'Authorization': f'ApiKey {API_KEY}'
}

# Make request with rate limit handling
def make_request(endpoint):
    response = requests.get(f'{BASE_URL}{endpoint}', headers=headers)
    
    # Check rate limit headers
    limit = response.headers.get('X-RateLimit-Limit')
    remaining = response.headers.get('X-RateLimit-Remaining')
    reset = response.headers.get('X-RateLimit-Reset')
    
    print(f'Rate Limit: {remaining}/{limit} (resets at {reset})')
    
    # Handle throttling
    if response.status_code == 429:
        retry_after = int(response.headers.get('Retry-After', 60))
        print(f'Throttled! Waiting {retry_after} seconds...')
        time.sleep(retry_after)
        return make_request(endpoint)  # Retry
    
    return response.json()

# Example usage
vehicles = make_request('/feed/vehicles/')
```

### JavaScript

```javascript
const API_KEY = 'key_abc123...';
const BASE_URL = 'http://localhost:8000/api';

async function makeRequest(endpoint) {
    const response = await fetch(`${BASE_URL}${endpoint}`, {
        headers: {
            'Authorization': `ApiKey ${API_KEY}`
        }
    });
    
    // Check rate limit headers
    const limit = response.headers.get('X-RateLimit-Limit');
    const remaining = response.headers.get('X-RateLimit-Remaining');
    const reset = response.headers.get('X-RateLimit-Reset');
    
    console.log(`Rate Limit: ${remaining}/${limit} (resets at ${reset})`);
    
    // Handle throttling
    if (response.status === 429) {
        const retryAfter = parseInt(response.headers.get('Retry-After') || '60');
        console.log(`Throttled! Waiting ${retryAfter} seconds...`);
        await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
        return makeRequest(endpoint); // Retry
    }
    
    return response.json();
}

// Example usage
const vehicles = await makeRequest('/feed/vehicles/');
```

### cURL with Rate Limit Monitoring

```bash
#!/bin/bash
API_KEY="key_abc123..."

# Function to make request and show rate limit headers
function api_request() {
    response=$(curl -s -D - \
        -H "Authorization: ApiKey $API_KEY" \
        "http://localhost:8000/api$1")
    
    # Extract headers
    limit=$(echo "$response" | grep -i "x-ratelimit-limit" | cut -d' ' -f2 | tr -d '\r')
    remaining=$(echo "$response" | grep -i "x-ratelimit-remaining" | cut -d' ' -f2 | tr -d '\r')
    reset=$(echo "$response" | grep -i "x-ratelimit-reset" | cut -d' ' -f2 | tr -d '\r')
    
    echo "Rate Limit: $remaining/$limit (resets at $reset)"
    
    # Show body
    echo "$response" | tail -1 | jq '.'
}

# Example usage
api_request "/feed/vehicles/"
```

## Troubleshooting

### Rate Limit Not Working

1. **Check middleware is enabled** in `settings.py`:
   ```python
   MIDDLEWARE = [
       ...
       'api.rate_limit_middleware.APIClientAuthMiddleware',
       'api.rate_limit_middleware.RateLimitHeaderMiddleware',
       'api.rate_limit_middleware.ClientUsageTrackingMiddleware',
   ]
   ```

2. **Check Redis is running**:
   ```bash
   docker-compose exec redis redis-cli ping
   # Should respond: PONG
   ```

3. **Check throttle classes are configured**:
   ```python
   REST_FRAMEWORK = {
       'DEFAULT_THROTTLE_CLASSES': [
           'api.throttling.GlobalAnonThrottle',
           ...
       ],
   }
   ```

### API Key Not Recognized

1. **Check key is active**:
   ```python
   from api.client_models import APIKey
   key = APIKey.objects.get(key_prefix='key_abc123...'[:12])
   print(f'Active: {key.is_active}')
   print(f'Valid: {key.is_valid()}')
   ```

2. **Check client is active**:
   ```python
   print(f'Client status: {key.client.status}')
   print(f'Client active: {key.client.is_active()}')
   ```

3. **Check header format**:
   ```bash
   # Correct
   Authorization: ApiKey key_abc123...
   
   # Wrong (missing space)
   Authorization: ApiKeykey_abc123...
   ```

### Metrics Not Recording

1. **Check middleware order** (should be last):
   ```python
   MIDDLEWARE = [
       ...
       'api.rate_limit_middleware.ClientUsageTrackingMiddleware',  # Last
   ]
   ```

2. **Check database connectivity**:
   ```bash
   docker-compose exec web python manage.py dbshell
   ```

3. **Check logs for errors**:
   ```bash
   docker-compose logs web | grep "Failed to track usage"
   ```

### Redis Connection Issues

1. **Check Redis config** in `settings.py`:
   ```python
   CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.redis.RedisCache',
           'LOCATION': 'redis://redis:6379/1',
       }
   }
   ```

2. **Test Redis connection**:
   ```bash
   docker-compose exec web python manage.py shell
   >>> from django.core.cache import cache
   >>> cache.set('test', 'value', 60)
   >>> cache.get('test')
   'value'
   ```

## Security Considerations

1. **API Key Protection**:
   - Never log API keys in plain text
   - Use headers (not query params) in production
   - Rotate keys regularly via admin interface

2. **Rate Limit Bypass**:
   - Don't disable throttling on public endpoints
   - Use per-client quotas for trusted integrations
   - Monitor `quota_violations` metric for abuse

3. **DDoS Protection**:
   - Burst limits prevent rapid attacks
   - IP-based limits for anonymous users
   - Consider adding firewall rules for extreme cases

4. **Data Privacy**:
   - Usage metrics don't store request content
   - Audit logs available for compliance
   - Configure data retention policies

## Performance Considerations

- **Redis Performance**: Can handle millions of requests/second
- **Middleware Overhead**: ~1-2ms per request
- **Database Queries**: Minimal (1 query per authenticated request)
- **Cache Efficiency**: Sliding windows prevent cache stampedes

## Compliance

The rate limiting system supports regulatory compliance:

- **Usage Tracking**: Complete audit trail in `ClientUsageMetrics`
- **Quota Enforcement**: Configurable per-client limits
- **Access Control**: API key authentication with revocation
- **Data Retention**: Automatic metrics archiving (configure in Celery tasks)

## Future Enhancements

Potential improvements for future iterations:

- [ ] Geographic rate limiting (per-region limits)
- [ ] Time-based quotas (business hours vs off-hours)
- [ ] Cost-based rate limiting (complex queries cost more)
- [ ] Quota increase requests workflow
- [ ] Real-time alerts for quota violations
- [ ] Rate limit analytics dashboard

## References

- Django REST Framework Throttling: https://www.django-rest-framework.org/api-guide/throttling/
- Redis Rate Limiting Patterns: https://redis.io/docs/manual/patterns/rate-limiter/
- HTTP 429 Status Code: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429
- X-RateLimit Headers: https://datatracker.ietf.org/doc/html/draft-polli-ratelimit-headers

## Support

For issues or questions:
1. Check this documentation
2. Review test suite for examples
3. Check application logs
4. Contact system administrator
