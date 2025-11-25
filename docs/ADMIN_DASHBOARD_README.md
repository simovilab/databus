# Admin Dashboard - Implementation Guide

## Overview

Complete admin panel with metrics dashboard, audit logging, and compliance features for managing API clients, monitoring usage, and tracking administrative actions.

## Features Implemented

### 1. **Admin Audit Logging** ✅
- Automatic tracking of all admin panel actions
- Captures views, additions, changes, and deletions
- Records user, IP address, user agent, and timestamps
- Before/after value tracking for changes
- Compliance-ready audit trail

### 2. **Metrics Dashboard** ✅
- Real-time overview of system metrics
- Interactive charts for traffic, latency, and errors
- Client distribution analytics
- Top clients by usage
- Recent events timeline

### 3. **Enhanced Admin Interface** ✅
- Improved client management views
- Bulk actions with audit logging
- Advanced filtering and search
- Export capabilities
- Color-coded status badges

## Components

### Models

#### `AdminAuditLog`
```python
# Location: api/client_models.py

class AdminAuditLog(models.Model):
    action_type      # Type of action (view, add, change, delete, etc.)
    content_type     # Type of object affected
    object_id        # ID of affected object
    object_repr      # String representation
    timestamp        # When action occurred
    user             # Admin user who performed action
    ip_address       # IP address of user
    user_agent       # Browser user agent
    changes          # JSON field with before/after values
    notes            # Additional notes
```

**Features:**
- Indexed on user, action_type, content_type, timestamp
- Helper method `log_action()` for easy logging
- Read-only in admin interface
- Only superusers can delete logs

### Middleware

#### `AdminAuditMiddleware`
```python
# Location: api/admin_audit.py

class AdminAuditMiddleware:
    - Captures all admin panel access
    - Logs view access (changelist, detail)
    - Records IP and user agent
    - Automatic logging without code changes
```

**Usage:**
Automatically logs when admins:
- View list pages
- View object details
- Access admin panels

### Dashboard Views

#### `admin_dashboard()`
Main dashboard with overview metrics and charts.

**Metrics Shown:**
- Total clients (active, pending, suspended)
- API keys (active, expired)
- Request count (24h)
- Error count (24h)
- Average latency (24h)
- Recent client events
- Recent admin actions
- Top clients by usage

#### `traffic_chart_data()`
API endpoint for traffic chart data.

**Parameters:**
- `period`: `24h`, `7d`, or `30d`

**Returns:**
```json
{
  "labels": ["00:00", "01:00", ...],
  "datasets": [
    {
      "label": "Requests",
      "data": [120, 150, 180, ...],
      "borderColor": "rgb(75, 192, 192)"
    },
    {
      "label": "Errors",
      "data": [2, 3, 1, ...],
      "borderColor": "rgb(255, 99, 132)"
    }
  ]
}
```

#### `latency_chart_data()`
API endpoint for latency metrics.

**Shows:**
- Average latency (ms)
- P95 latency (ms)
- P99 latency (ms)

#### `error_chart_data()`
API endpoint for error rates.

**Shows:**
- Error count
- Error rate (%)
- Dual Y-axis chart

#### `client_distribution_data()`
Client statistics by type and status.

#### `quota_usage_data()`
Quota usage for all clients with alerts.

### Admin Classes

#### `AdminAuditLogAdmin`
Enhanced admin interface for audit logs.

**Features:**
- Color-coded action badges
- User as clickable link
- Formatted changes display table
- Advanced filtering
- Date hierarchy
- Read-only interface

**Action Badge Colors:**
- View: Info (blue)
- Add: Success (green)
- Change: Warning (yellow)
- Delete: Danger (red)
- Export: Secondary (gray)
- Bulk Action: Purple
- Login/Logout: Teal/Orange
- Permission Change: Pink

### Templates

#### `admin/dashboard/overview.html`
Main dashboard template with:
- Responsive grid layout
- Metric cards
- Interactive charts (Chart.js)
- Period selectors (24h/7d/30d)
- Recent events timeline
- Top clients table

**Charts:**
1. **Traffic Overview**: Line chart with requests and errors
2. **Response Times**: Multi-line with avg, P95, P99
3. **Error Rates**: Dual-axis with count and rate

## Usage

### Accessing the Dashboard

1. **Admin Panel**: Navigate to `/admin/`
2. **Dashboard Link**: Navigate to `/admin/api/dashboard/`

Or add a link to your admin site:

```python
# In admin.py
from django.contrib import admin

admin.site.index_template = 'admin/custom_index.html'
```

### Logging Admin Actions

#### Automatic Logging
The middleware automatically logs:
- View access to changelists
- View access to object details

#### Manual Logging
For custom actions:

```python
from api.admin_audit import log_admin_action, log_model_change

# In ModelAdmin
def my_custom_action(self, request, queryset):
    # Perform action
    for obj in queryset:
        obj.do_something()
    
    # Log the action
    log_admin_action(self, request, queryset, 'my_custom_action')
    
    self.message_user(request, f"Action completed on {queryset.count()} items")

# In save_model
def save_model(self, request, obj, form, change):
    super().save_model(request, obj, form, change)
    
    action = 'change' if change else 'add'
    changes = {}
    
    if change:
        changes = {
            field: (form.initial.get(field), form.cleaned_data.get(field))
            for field in form.changed_data
        }
    
    log_model_change(obj, action, request.user, request, changes)
```

### Querying Audit Logs

```python
from api.models import AdminAuditLog
from django.contrib.auth.models import User

# Get all actions by a user
user = User.objects.get(username='admin')
actions = AdminAuditLog.objects.filter(user=user)

# Get all changes to clients
client_changes = AdminAuditLog.objects.filter(
    content_type='api.apiclient',
    action_type='change'
)

# Get actions in last 24 hours
from django.utils import timezone
from datetime import timedelta

recent = AdminAuditLog.objects.filter(
    timestamp__gte=timezone.now() - timedelta(hours=24)
)

# Get actions from specific IP
suspicious = AdminAuditLog.objects.filter(
    ip_address='192.168.1.100'
)
```

### Dashboard API Endpoints

All endpoints require staff authentication.

```bash
# Traffic data
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/admin/api/dashboard/traffic-data/?period=24h"

# Latency data
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/admin/api/dashboard/latency-data/?period=7d"

# Error data
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/admin/api/dashboard/error-data/?period=30d"

# Client distribution
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/admin/api/dashboard/client-distribution/"

# Quota usage
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/admin/api/dashboard/quota-usage/"
```

## Configuration

### Settings

```python
# realtime/settings.py

MIDDLEWARE = [
    # ... other middleware ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Add admin audit middleware
    "api.admin_audit.AdminAuditMiddleware",
    # ... rest of middleware ...
]
```

### URLs

```python
# api/urls.py

from . import admin_dashboard

urlpatterns = [
    # ... other URLs ...
    path("dashboard/", admin_dashboard.admin_dashboard, name="admin_dashboard"),
    path("dashboard/traffic-data/", admin_dashboard.traffic_chart_data),
    path("dashboard/latency-data/", admin_dashboard.latency_chart_data),
    path("dashboard/error-data/", admin_dashboard.error_chart_data),
]
```

## Security Features

### Access Control
- Dashboard requires staff member authentication (`@staff_member_required`)
- Audit logs visible only to staff
- Only superusers can delete audit logs

### Data Protection
- IP addresses captured for all actions
- User agent strings recorded
- Timestamps for all events
- Automatic truncation of long strings

### Compliance
- Immutable audit trail (read-only)
- Complete change history
- User attribution for all actions
- GDPR-compatible logging

## Monitoring & Alerts

### Key Metrics to Monitor

1. **Pending Approvals**
   - Alert when > 5 pending clients
   - Dashboard shows count with warning badge

2. **Suspended Clients**
   - Alert when any client suspended
   - Requires immediate attention

3. **Error Rates**
   - Alert when error rate > 5%
   - Shows in error chart

4. **Quota Usage**
   - Alert when client uses > 90% of quota
   - Quota usage endpoint provides data

5. **Admin Activity**
   - Monitor for suspicious actions
   - Review recent admin events

### Example Alert Configuration

```python
# In celery tasks or monitoring script
from api.models import APIClient, AdminAuditLog, ClientUsageMetrics
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta

def check_alerts():
    now = timezone.now()
    
    # Check pending approvals
    pending = APIClient.objects.filter(status='pending').count()
    if pending > 5:
        send_alert('High number of pending approvals', 
                   f'{pending} clients awaiting approval')
    
    # Check error rates
    last_hour = now - timedelta(hours=1)
    metrics = ClientUsageMetrics.objects.filter(timestamp__gte=last_hour)
    total_requests = sum(m.request_count for m in metrics)
    total_errors = sum(m.error_count for m in metrics)
    
    if total_requests > 0:
        error_rate = (total_errors / total_requests) * 100
        if error_rate > 5:
            send_alert('High error rate', 
                       f'Error rate is {error_rate:.2f}%')
    
    # Check suspicious admin activity
    suspicious_actions = AdminAuditLog.objects.filter(
        timestamp__gte=last_hour,
        action_type='delete'
    ).count()
    
    if suspicious_actions > 10:
        send_alert('Suspicious admin activity',
                   f'{suspicious_actions} deletions in last hour')
```

## Performance Considerations

### Database Indexes
All audit log queries use indexes on:
- `timestamp` (DESC)
- `user` + `timestamp`
- `action_type` + `timestamp`
- `content_type` + `timestamp`

### Chart Data Optimization
- Aggregation at database level
- Cached for 5 minutes (can be configured)
- Pagination for large datasets
- Efficient time-based truncation

### Audit Log Retention

```python
# Cleanup old audit logs (run monthly)
from api.models import AdminAuditLog
from django.utils import timezone
from datetime import timedelta

def cleanup_old_logs():
    cutoff = timezone.now() - timedelta(days=365)  # Keep 1 year
    deleted = AdminAuditLog.objects.filter(
        timestamp__lt=cutoff
    ).delete()
    return deleted[0]
```

## Testing

### Test Dashboard Access

```python
from django.test import TestCase, Client
from django.contrib.auth.models import User

class DashboardTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff',
            password='test123',
            is_staff=True
        )
    
    def test_dashboard_requires_auth(self):
        response = self.client.get('/admin/api/dashboard/')
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_dashboard_accessible_to_staff(self):
        self.client.login(username='staff', password='test123')
        response = self.client.get('/admin/api/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Admin Dashboard')
    
    def test_traffic_data_endpoint(self):
        self.client.login(username='staff', password='test123')
        response = self.client.get('/admin/api/dashboard/traffic-data/?period=24h')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('labels', data)
        self.assertIn('datasets', data)
```

### Test Audit Logging

```python
from api.models import AdminAuditLog, APIClient

class AuditLogTest(TestCase):
    def test_audit_log_creation(self):
        user = User.objects.create_user('test', password='test')
        
        log = AdminAuditLog.log_action(
            action_type='add',
            content_type='api.apiclient',
            object_repr='Test Client',
            user=user,
            ip_address='127.0.0.1'
        )
        
        self.assertEqual(log.action_type, 'add')
        self.assertEqual(log.user, user)
        self.assertIsNotNone(log.timestamp)
    
    def test_middleware_logs_view_access(self):
        self.client.login(username='staff', password='test123')
        
        before_count = AdminAuditLog.objects.count()
        self.client.get('/admin/api/apiclient/')
        after_count = AdminAuditLog.objects.count()
        
        self.assertEqual(after_count, before_count + 1)
```

## Troubleshooting

### Charts Not Loading

1. **Check JavaScript console** for errors
2. **Verify Chart.js CDN** is accessible
3. **Check API endpoints** return valid JSON
4. **Verify staff authentication**

```bash
# Test endpoint directly
curl -u admin:password http://localhost:8000/admin/api/dashboard/traffic-data/
```

### No Data in Charts

1. **Check ClientUsageMetrics** has data
2. **Verify date ranges** match data availability
3. **Check time zone** settings

```python
# Check if metrics exist
from api.models import ClientUsageMetrics
print(ClientUsageMetrics.objects.count())
print(ClientUsageMetrics.objects.latest('timestamp'))
```

### Audit Logs Not Appearing

1. **Verify middleware** is installed
2. **Check middleware order** (after AuthenticationMiddleware)
3. **Test with manual logging**

```python
from api.models import AdminAuditLog
from django.contrib.auth.models import User

user = User.objects.first()
AdminAuditLog.log_action(
    action_type='test',
    content_type='test.model',
    object_repr='Test',
    user=user
)
```

### Performance Issues

1. **Add database indexes** if missing
2. **Implement caching** for chart data
3. **Paginate** large result sets
4. **Archive** old audit logs

## Future Enhancements

### Planned Features
- [ ] Export audit logs to CSV/PDF
- [ ] Advanced filtering UI
- [ ] Custom alert rules
- [ ] Email notifications
- [ ] Real-time dashboard updates (WebSockets)
- [ ] Anomaly detection
- [ ] Predictive analytics
- [ ] Custom report builder
- [ ] Mobile-responsive improvements
- [ ] Dark mode

### Integration Opportunities
- Grafana/Prometheus for advanced metrics
- Elasticsearch for log analysis
- Slack/Teams for notifications
- SIEM systems for security monitoring

## References

- [Django Admin Documentation](https://docs.djangoproject.com/en/stable/ref/contrib/admin/)
- [Chart.js Documentation](https://www.chartjs.org/docs/)
- [Audit Logging Best Practices](https://owasp.org/www-community/Audit_Logging_Best_Practices)
- [GDPR Compliance](https://gdpr.eu/)

## Support

For issues or questions:
1. Check this documentation
2. Review audit logs for errors
3. Check Django admin logs
4. Contact system administrator

---

**Version:** 1.0.0  
**Last Updated:** 2025-11-25  
**Maintainer:** Databus Team
