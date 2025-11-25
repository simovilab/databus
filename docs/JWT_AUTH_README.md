# JWT Authentication and Role-Based Access Control (Issue #21)

## Overview

Databus implements secure JWT (JSON Web Token) authentication with role-based access control (RBAC) for API endpoints. This provides stateless, scalable authentication with granular permission management.

## Implementation Date
November 25, 2025

## Features

### 🔐 JWT Authentication
- **Stateless tokens**: No server-side session storage
- **Token rotation**: Automatic refresh token rotation for security
- **Custom claims**: User role, operator ID, company associations
- **Token expiration**: Configurable access (5 min) and refresh (1 day) token lifetimes
- **Blacklist support**: Revoke tokens on logout

### 👥 Role-Based Access Control (RBAC)
- **Roles**: admin, driver, dispatcher, user
- **Permission system**: Fine-grained access control per endpoint
- **Operator integration**: Link users to operator roles and companies
- **Staff privileges**: Django admin access for staff users

## Architecture

### JWT Token Flow
```
1. Login → POST /api/auth/token/
   ↓
2. Receive access + refresh tokens
   ↓
3. Include access token in Authorization header
   ↓
4. Token expires → POST /api/auth/token/refresh/
   ↓
5. Receive new access + refresh tokens (rotation)
```

### Token Structure

**Access Token Payload**:
```json
{
  "token_type": "access",
  "exp": 1732506000,
  "iat": 1732505700,
  "jti": "unique-token-id",
  "user_id": 1,
  "username": "john_doe",
  "role": "driver",
  "operator_id": 5,
  "companies": [1, 2],
  "is_staff": false
}
```

**Refresh Token**: Used only to obtain new access tokens

## API Endpoints

### POST `/api/auth/token/`
**Description**: Obtain JWT access and refresh tokens

**Request**:
```json
{
  "username": "john_doe",
  "password": "secure_password"
}
```

**Response** (200 OK):
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "driver",
    "operator_id": 5,
    "companies": [1, 2],
    "is_staff": false
  }
}
```

### POST `/api/auth/token/refresh/`
**Description**: Refresh access token using refresh token

**Request**:
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** (200 OK):
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Note**: Refresh token rotates on each refresh for enhanced security

### POST `/api/auth/verify/`
**Description**: Verify token validity and retrieve user info

**Request**:
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** (200 OK):
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "username": "john_doe",
    "role": "driver",
    "email": "john@example.com"
  }
}
```

**Response** (401 Unauthorized):
```json
{
  "detail": "Token is invalid or expired",
  "code": "token_not_valid"
}
```

### POST `/api/auth/logout/`
**Description**: Logout and blacklist refresh token

**Headers**:
```
Authorization: Bearer <access_token>
```

**Request**:
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** (200 OK):
```json
{
  "detail": "Logout successful"
}
```

## Usage Examples

### 1. Login and Get Tokens

```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "password": "secure_password"
  }'
```

### 2. Access Protected Endpoint

```bash
curl -X GET http://localhost:8000/api/clients/ \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 3. Refresh Token Before Expiration

```bash
curl -X POST http://localhost:8000/api/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'
```

### 4. Logout

```bash
curl -X POST http://localhost:8000/api/auth/logout/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh": "<refresh_token>"
  }'
```

## Python Client Example

```python
import requests

class DatabusClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
    
    def login(self, username, password):
        """Login and obtain tokens."""
        response = requests.post(
            f"{self.base_url}/api/auth/token/",
            json={"username": username, "password": password}
        )
        response.raise_for_status()
        data = response.json()
        
        self.access_token = data["access"]
        self.refresh_token = data["refresh"]
        return data["user"]
    
    def refresh(self):
        """Refresh access token."""
        response = requests.post(
            f"{self.base_url}/api/auth/token/refresh/",
            json={"refresh": self.refresh_token}
        )
        response.raise_for_status()
        data = response.json()
        
        self.access_token = data["access"]
        self.refresh_token = data["refresh"]
    
    def get(self, endpoint):
        """Make authenticated GET request."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.get(f"{self.base_url}{endpoint}", headers=headers)
        
        # Auto-refresh on 401
        if response.status_code == 401:
            self.refresh()
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{self.base_url}{endpoint}", headers=headers)
        
        response.raise_for_status()
        return response.json()
    
    def logout(self):
        """Logout and blacklist tokens."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        requests.post(
            f"{self.base_url}/api/auth/logout/",
            headers=headers,
            json={"refresh": self.refresh_token}
        )
        self.access_token = None
        self.refresh_token = None

# Usage
client = DatabusClient()
user = client.login("john_doe", "secure_password")
print(f"Logged in as {user['username']} with role {user['role']}")

# Make authenticated requests
clients = client.get("/api/clients/")
print(f"Found {len(clients)} API clients")

# Logout
client.logout()
```

## Role-Based Permissions

### Permission Classes

**IsAdminRole**: Only admin users
```python
from api.permissions import IsAdminRole

class MyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminRole]
```

**IsDriverRole**: Only drivers
```python
from api.permissions import IsDriverRole

class VehicleLocationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsDriverRole]
```

**IsDispatcherRole**: Only dispatchers
```python
from api.permissions import IsDispatcherRole

class TripManagementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsDispatcherRole]
```

**IsAdminOrReadOnly**: Admins can write, others read-only
```python
from api.permissions import IsAdminOrReadOnly

class RouteViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
```

### Role Hierarchy
```
admin > dispatcher > driver > user
```

### Default Permissions by Role

| Endpoint | Admin | Dispatcher | Driver | User |
|----------|-------|------------|--------|------|
| Read GTFS data | ✅ | ✅ | ✅ | ✅ |
| Create/Update Routes | ✅ | ✅ | ❌ | ❌ |
| Manage Trips | ✅ | ✅ | ❌ | ❌ |
| Update Vehicle Location | ✅ | ✅ | ✅ | ❌ |
| API Client Management | ✅ | ❌ | ❌ | ❌ |
| User Management | ✅ | ❌ | ❌ | ❌ |

## Configuration

### settings.py

```python
from datetime import timedelta

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
}

# DRF Authentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}
```

## Security Best Practices

1. **HTTPS Only**: Always use HTTPS in production
2. **Short Access Token Lifetime**: 5-15 minutes recommended
3. **Token Rotation**: Enable refresh token rotation
4. **Blacklist Tokens**: Blacklist refresh tokens on logout
5. **Secure Storage**: Store tokens securely (httpOnly cookies or secure storage)
6. **CORS Configuration**: Restrict origins in production
7. **Rate Limiting**: Implement rate limiting on auth endpoints

## Error Handling

### Common Errors

**401 Unauthorized - Invalid Credentials**:
```json
{
  "detail": "No active account found with the given credentials"
}
```

**401 Unauthorized - Expired Token**:
```json
{
  "detail": "Token is invalid or expired",
  "code": "token_not_valid"
}
```

**401 Unauthorized - Blacklisted Token**:
```json
{
  "detail": "Token is blacklisted",
  "code": "token_not_valid"
}
```

**403 Forbidden - Insufficient Permissions**:
```json
{
  "detail": "You do not have permission to perform this action."
}
```

## Testing

### Unit Tests
```bash
pytest tests/test_jwt.py -v
```

### Test JWT Authentication
```python
import pytest
from rest_framework.test import APIClient

def test_jwt_login():
    client = APIClient()
    response = client.post('/api/auth/token/', {
        'username': 'testuser',
        'password': 'testpass123'
    })
    assert response.status_code == 200
    assert 'access' in response.data
    assert 'refresh' in response.data
```

## Migration from Session Auth

If migrating from session-based authentication:

1. **Dual Authentication**: Support both JWT and session auth temporarily
```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
}
```

2. **Client Migration**: Update clients to use JWT tokens
3. **Remove Session Auth**: Once all clients migrated, remove session auth

## Troubleshooting

### Token Expired Immediately
- Check server time synchronization
- Verify `ACCESS_TOKEN_LIFETIME` setting

### 401 on Valid Token
- Check `Authorization` header format: `Bearer <token>`
- Verify token hasn't been blacklisted
- Check signature algorithm matches

### Refresh Token Not Working
- Ensure `ROTATE_REFRESH_TOKENS = True`
- Check refresh token hasn't expired
- Verify token hasn't been blacklisted

## Related Documentation

- [API Client Registry](CLIENT_REGISTRY_README.md)
- [Rate Limiting](RATE_LIMITING_README.md)
- [Security & Performance](SECURITY_PERFORMANCE_README.md)
- [Testing Guide](testing.md)

## References

- [djangorestframework-simplejwt Documentation](https://django-rest-framework-simplejwt.readthedocs.io/)
- [JWT.io](https://jwt.io/)
- [RFC 7519: JSON Web Token (JWT)](https://tools.ietf.org/html/rfc7519)
