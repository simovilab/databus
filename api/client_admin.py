"""
Django Admin for API Client Registry and Lifecycle Management.
"""
from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from django.utils.safestring import mark_safe
from .client_models import (
    APIClient,
    APIKey,
    ClientQuota,
    ClientUsageMetrics,
    ClientAuditLog,
    AdminAuditLog,
)


class APIKeyInline(admin.TabularInline):
    """Inline admin for API keys."""
    model = APIKey
    extra = 0
    readonly_fields = ('key_id', 'key_prefix', 'created_at', 'last_used_at', 'is_active')
    fields = ('name', 'key_id', 'key_prefix', 'is_active', 'expires_at', 'created_at', 'last_used_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


class ClientQuotaInline(admin.StackedInline):
    """Inline admin for client quotas."""
    model = ClientQuota
    can_delete = False
    fieldsets = (
        ('Rate Limits', {
            'fields': ('requests_per_minute', 'requests_per_hour', 'requests_per_day')
        }),
        ('Data Limits', {
            'fields': ('max_data_points_per_request', 'max_concurrent_connections')
        }),
        ('Features', {
            'fields': ('can_write', 'can_subscribe_realtime', 'can_access_historical')
        }),
        ('Alerts', {
            'fields': ('warning_threshold',)
        }),
    )


class ClientAuditLogInline(admin.TabularInline):
    """Inline admin for audit logs."""
    model = ClientAuditLog
    extra = 0
    readonly_fields = ('timestamp', 'event_type', 'performed_by', 'description', 'ip_address')
    fields = ('timestamp', 'event_type', 'performed_by', 'description')
    can_delete = False
    ordering = ('-timestamp',)
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(APIClient)
class APIClientAdmin(admin.ModelAdmin):
    """Admin interface for API clients."""
    list_display = (
        'client_name',
        'client_id_short',
        'client_type',
        'owner',
        'status_badge',
        'created_at',
        'total_requests',
        'actions_column',
    )
    list_filter = (
        'status',
        'client_type',
        'created_at',
        'approved_at',
    )
    search_fields = (
        'client_id',
        'client_name',
        'owner__username',
        'owner__email',
        'contact_email',
        'organization',
    )
    readonly_fields = (
        'client_id',
        'created_at',
        'updated_at',
        'approved_at',
        'approved_by',
        'disabled_at',
        'total_requests_display',
        'success_rate_display',
    )
    
    fieldsets = (
        ('Identification', {
            'fields': ('client_id', 'client_name', 'client_type', 'description')
        }),
        ('Ownership', {
            'fields': ('owner', 'organization', 'contact_email')
        }),
        ('Status', {
            'fields': ('status', 'approved_at', 'approved_by', 'disabled_at', 'disabled_reason')
        }),
        ('Access Control', {
            'fields': ('allowed_ips',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Usage Statistics', {
            'fields': ('total_requests_display', 'success_rate_display'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [ClientQuotaInline, APIKeyInline, ClientAuditLogInline]
    
    actions = ['approve_clients', 'suspend_clients', 'activate_clients', 'revoke_clients']
    
    def client_id_short(self, obj):
        """Display shortened client ID."""
        return f"{obj.client_id[:20]}..."
    client_id_short.short_description = 'Client ID'
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'pending': 'orange',
            'active': 'green',
            'suspended': 'yellow',
            'disabled': 'gray',
            'revoked': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def total_requests(self, obj):
        """Display total requests count."""
        total = obj.usage_metrics.aggregate(
            total=models.Sum('total_requests')
        )['total'] or 0
        return f"{total:,}"
    total_requests.short_description = 'Total Requests'
    
    def total_requests_display(self, obj):
        """Display total requests in detail view."""
        metrics = obj.usage_metrics.aggregate(
            total=models.Sum('total_requests'),
            successful=models.Sum('successful_requests'),
            failed=models.Sum('failed_requests')
        )
        return format_html(
            'Total: {:,} | Successful: {:,} | Failed: {:,}',
            metrics['total'] or 0,
            metrics['successful'] or 0,
            metrics['failed'] or 0
        )
    total_requests_display.short_description = 'Total Requests'
    
    def success_rate_display(self, obj):
        """Display success rate."""
        metrics = obj.usage_metrics.aggregate(
            total=models.Sum('total_requests'),
            successful=models.Sum('successful_requests')
        )
        total = metrics['total'] or 0
        successful = metrics['successful'] or 0
        if total == 0:
            return 'N/A'
        rate = (successful / total) * 100
        color = 'green' if rate >= 95 else 'orange' if rate >= 80 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f}%</span>',
            color,
            rate
        )
    success_rate_display.short_description = 'Success Rate'
    
    def actions_column(self, obj):
        """Display action buttons."""
        buttons = []
        
        if obj.status == 'pending':
            buttons.append(
                '<a class="button" href="#" onclick="return false;" '
                'style="background-color: green; color: white; padding: 3px 10px; '
                'border-radius: 3px; text-decoration: none; margin-right: 5px;">Approve</a>'
            )
        
        if obj.status == 'active':
            buttons.append(
                '<a class="button" href="#" onclick="return false;" '
                'style="background-color: orange; color: white; padding: 3px 10px; '
                'border-radius: 3px; text-decoration: none; margin-right: 5px;">Suspend</a>'
            )
        
        if obj.status in ['suspended', 'disabled']:
            buttons.append(
                '<a class="button" href="#" onclick="return false;" '
                'style="background-color: green; color: white; padding: 3px 10px; '
                'border-radius: 3px; text-decoration: none; margin-right: 5px;">Activate</a>'
            )
        
        return mark_safe(''.join(buttons))
    actions_column.short_description = 'Actions'
    
    def approve_clients(self, request, queryset):
        """Bulk approve clients."""
        count = 0
        for client in queryset.filter(status='pending'):
            client.activate(approved_by=request.user)
            ClientAuditLog.log_event(
                client=client,
                event_type='approved',
                performed_by=request.user,
                description=f'Client approved by {request.user.username}'
            )
            count += 1
        self.message_user(request, f'{count} client(s) approved successfully.')
    approve_clients.short_description = 'Approve selected clients'
    
    def suspend_clients(self, request, queryset):
        """Bulk suspend clients."""
        count = 0
        for client in queryset.filter(status='active'):
            client.suspend(reason='Suspended by admin')
            ClientAuditLog.log_event(
                client=client,
                event_type='suspended',
                performed_by=request.user,
                description=f'Client suspended by {request.user.username}'
            )
            count += 1
        self.message_user(request, f'{count} client(s) suspended.')
    suspend_clients.short_description = 'Suspend selected clients'
    
    def activate_clients(self, request, queryset):
        """Bulk activate clients."""
        count = 0
        for client in queryset.exclude(status__in=['active', 'revoked']):
            client.activate(approved_by=request.user)
            ClientAuditLog.log_event(
                client=client,
                event_type='activated',
                performed_by=request.user,
                description=f'Client activated by {request.user.username}'
            )
            count += 1
        self.message_user(request, f'{count} client(s) activated.')
    activate_clients.short_description = 'Activate selected clients'
    
    def revoke_clients(self, request, queryset):
        """Bulk revoke clients."""
        count = 0
        for client in queryset.exclude(status='revoked'):
            client.revoke(reason='Revoked by admin')
            ClientAuditLog.log_event(
                client=client,
                event_type='revoked',
                performed_by=request.user,
                description=f'Client revoked by {request.user.username}'
            )
            count += 1
        self.message_user(request, f'{count} client(s) revoked.')
    revoke_clients.short_description = 'Revoke selected clients'
    
    def save_model(self, request, obj, form, change):
        """Log client creation/updates."""
        is_new = obj.pk is None
        super().save_model(request, obj, form, change)
        
        if is_new:
            ClientAuditLog.log_event(
                client=obj,
                event_type='created',
                performed_by=request.user,
                description=f'Client created by {request.user.username}'
            )


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    """Admin interface for API keys."""
    list_display = (
        'key_prefix_display',
        'client',
        'name',
        'is_active',
        'created_at',
        'expires_at',
        'last_used_at',
        'actions_column',
    )
    list_filter = (
        'is_active',
        'created_at',
        'expires_at',
    )
    search_fields = (
        'key_id',
        'key_prefix',
        'client__client_name',
        'client__client_id',
        'name',
    )
    readonly_fields = (
        'key_id',
        'key_hash',
        'key_prefix',
        'created_at',
        'last_used_at',
        'revoked_at',
    )
    
    fieldsets = (
        ('Key Information', {
            'fields': ('key_id', 'key_prefix', 'key_hash', 'name')
        }),
        ('Association', {
            'fields': ('client',)
        }),
        ('Status', {
            'fields': ('is_active', 'expires_at', 'revoked_at')
        }),
        ('Usage', {
            'fields': ('created_at', 'last_used_at')
        }),
    )
    
    actions = ['revoke_keys', 'activate_keys']
    
    def key_prefix_display(self, obj):
        """Display key prefix."""
        return f"{obj.key_prefix}..."
    key_prefix_display.short_description = 'Key'
    
    def actions_column(self, obj):
        """Display action buttons."""
        if obj.is_active:
            return format_html(
                '<a class="button" href="#" onclick="return false;" '
                'style="background-color: red; color: white; padding: 3px 10px; '
                'border-radius: 3px; text-decoration: none;">Revoke</a>'
            )
        return format_html('<span style="color: gray;">Revoked</span>')
    actions_column.short_description = 'Actions'
    
    def revoke_keys(self, request, queryset):
        """Bulk revoke API keys."""
        count = 0
        for key in queryset.filter(is_active=True):
            key.revoke()
            ClientAuditLog.log_event(
                client=key.client,
                event_type='key_revoked',
                performed_by=request.user,
                description=f'API key {key.key_prefix}... revoked by {request.user.username}',
                metadata={'key_id': key.key_id}
            )
            count += 1
        self.message_user(request, f'{count} API key(s) revoked.')
    revoke_keys.short_description = 'Revoke selected API keys'
    
    def activate_keys(self, request, queryset):
        """Bulk activate API keys."""
        count = queryset.filter(is_active=False, revoked_at__isnull=True).update(is_active=True)
        self.message_user(request, f'{count} API key(s) activated.')
    activate_keys.short_description = 'Activate selected API keys'
    
    def has_add_permission(self, request):
        """Disable manual key creation (use API endpoint)."""
        return False


@admin.register(ClientQuota)
class ClientQuotaAdmin(admin.ModelAdmin):
    """Admin interface for client quotas."""
    list_display = (
        'client',
        'requests_per_minute',
        'requests_per_hour',
        'requests_per_day',
        'can_write',
        'can_subscribe_realtime',
    )
    list_filter = (
        'can_write',
        'can_subscribe_realtime',
        'can_access_historical',
    )
    search_fields = (
        'client__client_name',
        'client__client_id',
    )
    
    fieldsets = (
        ('Client', {
            'fields': ('client',)
        }),
        ('Rate Limits', {
            'fields': ('requests_per_minute', 'requests_per_hour', 'requests_per_day')
        }),
        ('Data Limits', {
            'fields': ('max_data_points_per_request', 'max_concurrent_connections')
        }),
        ('Features', {
            'fields': ('can_write', 'can_subscribe_realtime', 'can_access_historical')
        }),
        ('Alerts', {
            'fields': ('warning_threshold',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Log quota updates."""
        super().save_model(request, obj, form, change)
        
        if change:
            ClientAuditLog.log_event(
                client=obj.client,
                event_type='quota_updated',
                performed_by=request.user,
                description=f'Quota updated by {request.user.username}',
                metadata={'limits': obj.get_limits()}
            )


@admin.register(ClientUsageMetrics)
class ClientUsageMetricsAdmin(admin.ModelAdmin):
    """Admin interface for usage metrics."""
    list_display = (
        'client',
        'period_type',
        'period_start',
        'total_requests',
        'success_rate_display',
        'avg_response_time',
        'quota_violations',
    )
    list_filter = (
        'period_type',
        'period_start',
    )
    search_fields = (
        'client__client_name',
        'client__client_id',
    )
    readonly_fields = (
        'client',
        'period_start',
        'period_end',
        'period_type',
        'total_requests',
        'successful_requests',
        'failed_requests',
        'data_points_read',
        'data_points_written',
        'avg_response_time',
        'max_response_time',
        'quota_violations',
        'bytes_sent',
        'bytes_received',
        'websocket_connections',
        'websocket_messages',
        'created_at',
        'success_rate_display',
    )
    
    fieldsets = (
        ('Client & Period', {
            'fields': ('client', 'period_type', 'period_start', 'period_end')
        }),
        ('Request Metrics', {
            'fields': ('total_requests', 'successful_requests', 'failed_requests', 'success_rate_display')
        }),
        ('Data Metrics', {
            'fields': ('data_points_read', 'data_points_written')
        }),
        ('Performance', {
            'fields': ('avg_response_time', 'max_response_time')
        }),
        ('Quota & Violations', {
            'fields': ('quota_violations',)
        }),
        ('Bandwidth', {
            'fields': ('bytes_sent', 'bytes_received'),
            'classes': ('collapse',)
        }),
        ('WebSocket', {
            'fields': ('websocket_connections', 'websocket_messages'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def success_rate_display(self, obj):
        """Display success rate."""
        rate = obj.success_rate()
        color = 'green' if rate >= 95 else 'orange' if rate >= 80 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f}%</span>',
            color,
            rate
        )
    success_rate_display.short_description = 'Success Rate'
    
    def has_add_permission(self, request):
        """Metrics are created automatically."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Don't allow deletion of metrics."""
        return False


@admin.register(ClientAuditLog)
class ClientAuditLogAdmin(admin.ModelAdmin):
    """Admin interface for audit logs."""
    list_display = (
        'timestamp',
        'client',
        'event_type',
        'performed_by',
        'ip_address',
    )
    list_filter = (
        'event_type',
        'timestamp',
    )
    search_fields = (
        'client__client_name',
        'client__client_id',
        'performed_by__username',
        'description',
        'ip_address',
    )
    readonly_fields = (
        'client',
        'event_type',
        'timestamp',
        'performed_by',
        'description',
        'metadata',
        'ip_address',
        'user_agent',
    )
    
    fieldsets = (
        ('Event', {
            'fields': ('client', 'event_type', 'timestamp')
        }),
        ('Actor', {
            'fields': ('performed_by', 'ip_address', 'user_agent')
        }),
        ('Details', {
            'fields': ('description', 'metadata')
        }),
    )
    
    def has_add_permission(self, request):
        """Logs are created automatically."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Don't allow deletion of audit logs."""
        return False


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    """
    Admin interface for administrative audit logs.
    
    Provides read-only access to all administrative actions performed
    in the admin panel for compliance and security monitoring.
    """
    list_display = (
        'timestamp',
        'user_link',
        'action_badge',
        'content_type',
        'object_repr_short',
        'ip_address',
    )
    list_filter = (
        'action_type',
        'content_type',
        'timestamp',
        'user',
    )
    search_fields = (
        'user__username',
        'user__email',
        'object_repr',
        'content_type',
        'ip_address',
        'notes',
    )
    readonly_fields = (
        'timestamp',
        'action_type',
        'content_type',
        'object_id',
        'object_repr',
        'user',
        'ip_address',
        'user_agent',
        'changes_display',
        'notes',
    )
    fieldsets = (
        ('Action Details', {
            'fields': ('timestamp', 'action_type', 'user')
        }),
        ('Target Object', {
            'fields': ('content_type', 'object_id', 'object_repr')
        }),
        ('Context', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Changes', {
            'fields': ('changes_display', 'notes'),
            'classes': ('collapse',)
        }),
    )
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    
    def user_link(self, obj):
        """Display user as clickable link."""
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return format_html('<em>System</em>')
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'
    
    def action_badge(self, obj):
        """Display action type as colored badge."""
        colors = {
            'view': '#17a2b8',      # info
            'add': '#28a745',       # success
            'change': '#ffc107',    # warning
            'delete': '#dc3545',    # danger
            'export': '#6c757d',    # secondary
            'bulk_action': '#6f42c1', # purple
            'login': '#20c997',     # teal
            'logout': '#fd7e14',    # orange
            'permission_change': '#e83e8c', # pink
        }
        color = colors.get(obj.action_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_action_type_display()
        )
    action_badge.short_description = 'Action'
    action_badge.admin_order_field = 'action_type'
    
    def object_repr_short(self, obj):
        """Display shortened object representation."""
        if len(obj.object_repr) > 50:
            return obj.object_repr[:47] + '...'
        return obj.object_repr
    object_repr_short.short_description = 'Object'
    
    def changes_display(self, obj):
        """Display changes in readable format."""
        if not obj.changes:
            return format_html('<em>No changes recorded</em>')
        
        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background-color: #f8f9fa;"><th style="padding: 8px; text-align: left; border: 1px solid #dee2e6;">Field</th>'
        html += '<th style="padding: 8px; text-align: left; border: 1px solid #dee2e6;">Before</th>'
        html += '<th style="padding: 8px; text-align: left; border: 1px solid #dee2e6;">After</th></tr>'
        
        for field, values in obj.changes.items():
            if isinstance(values, (list, tuple)) and len(values) == 2:
                before, after = values
            else:
                before, after = '-', str(values)
            
            html += f'<tr><td style="padding: 8px; border: 1px solid #dee2e6;"><strong>{field}</strong></td>'
            html += f'<td style="padding: 8px; border: 1px solid #dee2e6;">{before}</td>'
            html += f'<td style="padding: 8px; border: 1px solid #dee2e6;">{after}</td></tr>'
        
        html += '</table>'
        return format_html(html)
    changes_display.short_description = 'Changes Made'
    
    def has_add_permission(self, request):
        """Audit logs are created automatically."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Audit logs are read-only."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Don't allow deletion of audit logs."""
        return request.user.is_superuser  # Only superusers can delete
