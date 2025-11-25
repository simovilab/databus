"""
Admin Dashboard Views

Provides custom admin dashboard views with metrics, charts, and analytics.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Count, Avg, Sum, Q, F
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from datetime import timedelta
from api.models import (
    APIClient, APIKey, ClientQuota, ClientUsageMetrics,
    ClientAuditLog, AdminAuditLog, ClientStatus
)


@staff_member_required
def admin_dashboard(request):
    """
    Main admin dashboard with overview metrics and charts.
    """
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)
    
    # Client statistics
    total_clients = APIClient.objects.count()
    active_clients = APIClient.objects.filter(status=ClientStatus.ACTIVE).count()
    pending_clients = APIClient.objects.filter(status=ClientStatus.PENDING).count()
    suspended_clients = APIClient.objects.filter(status=ClientStatus.SUSPENDED).count()
    
    # API Key statistics
    total_keys = APIKey.objects.count()
    active_keys = APIKey.objects.filter(is_active=True, revoked_at__isnull=True).count()
    expired_keys = APIKey.objects.filter(expires_at__lt=now).count()
    
    # Usage statistics (last 24 hours)
    usage_24h = ClientUsageMetrics.objects.filter(
        timestamp__gte=last_24h
    ).aggregate(
        total_requests=Sum('request_count'),
        total_errors=Sum('error_count'),
        avg_latency=Avg('avg_response_time')
    )
    
    # Recent audit events
    recent_client_events = ClientAuditLog.objects.select_related('client', 'performed_by')[:10]
    recent_admin_events = AdminAuditLog.objects.select_related('user')[:10]
    
    # Clients by type
    clients_by_type = APIClient.objects.values('client_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Top clients by usage (last 7 days)
    top_clients = ClientUsageMetrics.objects.filter(
        timestamp__gte=last_7d
    ).values(
        'client__client_name',
        'client__id'
    ).annotate(
        total_requests=Sum('request_count')
    ).order_by('-total_requests')[:10]
    
    context = {
        'total_clients': total_clients,
        'active_clients': active_clients,
        'pending_clients': pending_clients,
        'suspended_clients': suspended_clients,
        'total_keys': total_keys,
        'active_keys': active_keys,
        'expired_keys': expired_keys,
        'usage_24h': usage_24h,
        'recent_client_events': recent_client_events,
        'recent_admin_events': recent_admin_events,
        'clients_by_type': clients_by_type,
        'top_clients': top_clients,
    }
    
    return render(request, 'admin/dashboard/overview.html', context)


@staff_member_required
def traffic_chart_data(request):
    """
    API endpoint for traffic chart data.
    Returns request counts over time.
    """
    period = request.GET.get('period', '24h')  # 24h, 7d, 30d
    
    now = timezone.now()
    if period == '24h':
        start_time = now - timedelta(hours=24)
        trunc_func = TruncHour
    elif period == '7d':
        start_time = now - timedelta(days=7)
        trunc_func = TruncDate
    else:  # 30d
        start_time = now - timedelta(days=30)
        trunc_func = TruncDate
    
    # Aggregate request counts by time period
    traffic_data = ClientUsageMetrics.objects.filter(
        timestamp__gte=start_time
    ).annotate(
        period=trunc_func('timestamp')
    ).values('period').annotate(
        requests=Sum('request_count'),
        errors=Sum('error_count')
    ).order_by('period')
    
    # Format for Chart.js
    labels = []
    requests_data = []
    errors_data = []
    
    for item in traffic_data:
        if period == '24h':
            labels.append(item['period'].strftime('%H:%M'))
        else:
            labels.append(item['period'].strftime('%Y-%m-%d'))
        requests_data.append(item['requests'] or 0)
        errors_data.append(item['errors'] or 0)
    
    return JsonResponse({
        'labels': labels,
        'datasets': [
            {
                'label': 'Requests',
                'data': requests_data,
                'borderColor': 'rgb(75, 192, 192)',
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'tension': 0.1
            },
            {
                'label': 'Errors',
                'data': errors_data,
                'borderColor': 'rgb(255, 99, 132)',
                'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                'tension': 0.1
            }
        ]
    })


@staff_member_required
def latency_chart_data(request):
    """
    API endpoint for latency chart data.
    Returns average response times over time.
    """
    period = request.GET.get('period', '24h')
    
    now = timezone.now()
    if period == '24h':
        start_time = now - timedelta(hours=24)
        trunc_func = TruncHour
    elif period == '7d':
        start_time = now - timedelta(days=7)
        trunc_func = TruncDate
    else:  # 30d
        start_time = now - timedelta(days=30)
        trunc_func = TruncDate
    
    # Aggregate latency by time period
    latency_data = ClientUsageMetrics.objects.filter(
        timestamp__gte=start_time,
        avg_response_time__isnull=False
    ).annotate(
        period=trunc_func('timestamp')
    ).values('period').annotate(
        avg_latency=Avg('avg_response_time'),
        p95_latency=Avg('p95_response_time'),
        p99_latency=Avg('p99_response_time')
    ).order_by('period')
    
    # Format for Chart.js
    labels = []
    avg_data = []
    p95_data = []
    p99_data = []
    
    for item in latency_data:
        if period == '24h':
            labels.append(item['period'].strftime('%H:%M'))
        else:
            labels.append(item['period'].strftime('%Y-%m-%d'))
        avg_data.append(round(item['avg_latency'] or 0, 2))
        p95_data.append(round(item['p95_latency'] or 0, 2))
        p99_data.append(round(item['p99_latency'] or 0, 2))
    
    return JsonResponse({
        'labels': labels,
        'datasets': [
            {
                'label': 'Average Latency (ms)',
                'data': avg_data,
                'borderColor': 'rgb(54, 162, 235)',
                'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                'tension': 0.1
            },
            {
                'label': 'P95 Latency (ms)',
                'data': p95_data,
                'borderColor': 'rgb(255, 206, 86)',
                'backgroundColor': 'rgba(255, 206, 86, 0.2)',
                'tension': 0.1
            },
            {
                'label': 'P99 Latency (ms)',
                'data': p99_data,
                'borderColor': 'rgb(255, 159, 64)',
                'backgroundColor': 'rgba(255, 159, 64, 0.2)',
                'tension': 0.1
            }
        ]
    })


@staff_member_required
def error_chart_data(request):
    """
    API endpoint for error rate chart data.
    Returns error counts and rates over time.
    """
    period = request.GET.get('period', '24h')
    
    now = timezone.now()
    if period == '24h':
        start_time = now - timedelta(hours=24)
        trunc_func = TruncHour
    elif period == '7d':
        start_time = now - timedelta(days=7)
        trunc_func = TruncDate
    else:  # 30d
        start_time = now - timedelta(days=30)
        trunc_func = TruncDate
    
    # Aggregate errors by time period
    error_data = ClientUsageMetrics.objects.filter(
        timestamp__gte=start_time
    ).annotate(
        period=trunc_func('timestamp')
    ).values('period').annotate(
        total_requests=Sum('request_count'),
        total_errors=Sum('error_count')
    ).order_by('period')
    
    # Calculate error rates
    labels = []
    error_counts = []
    error_rates = []
    
    for item in error_data:
        if period == '24h':
            labels.append(item['period'].strftime('%H:%M'))
        else:
            labels.append(item['period'].strftime('%Y-%m-%d'))
        
        errors = item['total_errors'] or 0
        requests = item['total_requests'] or 0
        rate = (errors / requests * 100) if requests > 0 else 0
        
        error_counts.append(errors)
        error_rates.append(round(rate, 2))
    
    return JsonResponse({
        'labels': labels,
        'datasets': [
            {
                'label': 'Error Count',
                'data': error_counts,
                'borderColor': 'rgb(255, 99, 132)',
                'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                'yAxisID': 'y',
                'tension': 0.1
            },
            {
                'label': 'Error Rate (%)',
                'data': error_rates,
                'borderColor': 'rgb(153, 102, 255)',
                'backgroundColor': 'rgba(153, 102, 255, 0.2)',
                'yAxisID': 'y1',
                'tension': 0.1
            }
        ]
    })


@staff_member_required
def client_distribution_data(request):
    """
    API endpoint for client distribution data.
    Returns client counts by type and status.
    """
    # Clients by type
    by_type = list(APIClient.objects.values('client_type').annotate(
        count=Count('id')
    ).order_by('-count'))
    
    # Clients by status
    by_status = list(APIClient.objects.values('status').annotate(
        count=Count('id')
    ).order_by('-count'))
    
    return JsonResponse({
        'by_type': {
            'labels': [item['client_type'] for item in by_type],
            'data': [item['count'] for item in by_type]
        },
        'by_status': {
            'labels': [item['status'] for item in by_status],
            'data': [item['count'] for item in by_status]
        }
    })


@staff_member_required
def quota_usage_data(request):
    """
    API endpoint for quota usage statistics.
    Returns clients approaching or exceeding quotas.
    """
    # Get quotas with current usage
    quotas = ClientQuota.objects.select_related('client').all()
    
    quota_data = []
    for quota in quotas:
        # Get recent usage
        now = timezone.now()
        usage_day = ClientUsageMetrics.objects.filter(
            client=quota.client,
            timestamp__gte=now - timedelta(days=1)
        ).aggregate(total=Sum('request_count'))['total'] or 0
        
        if quota.requests_per_day:
            usage_pct = (usage_day / quota.requests_per_day * 100)
            quota_data.append({
                'client_name': quota.client.client_name,
                'quota': quota.requests_per_day,
                'used': usage_day,
                'percentage': round(usage_pct, 1)
            })
    
    # Sort by usage percentage
    quota_data.sort(key=lambda x: x['percentage'], reverse=True)
    
    return JsonResponse({
        'quotas': quota_data[:20]  # Top 20
    })
