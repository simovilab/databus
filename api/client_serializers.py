"""
Serializers for API Client Registry and Lifecycle Management.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .client_models import (
    APIClient,
    APIKey,
    ClientQuota,
    ClientUsageMetrics,
    ClientAuditLog,
)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class ClientQuotaSerializer(serializers.ModelSerializer):
    """Serializer for ClientQuota model."""
    limits = serializers.SerializerMethodField()
    
    class Meta:
        model = ClientQuota
        fields = [
            'requests_per_minute',
            'requests_per_hour',
            'requests_per_day',
            'max_data_points_per_request',
            'max_concurrent_connections',
            'can_write',
            'can_subscribe_realtime',
            'can_access_historical',
            'warning_threshold',
            'limits',
        ]
    
    def get_limits(self, obj):
        """Get all limits as a dictionary."""
        return obj.get_limits()


class APIKeySerializer(serializers.ModelSerializer):
    """Serializer for APIKey model (without exposing secret)."""
    key_display = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()
    
    class Meta:
        model = APIKey
        fields = [
            'key_id',
            'key_display',
            'name',
            'is_active',
            'is_valid',
            'created_at',
            'expires_at',
            'days_until_expiry',
            'last_used_at',
            'revoked_at',
        ]
        read_only_fields = [
            'key_id',
            'created_at',
            'last_used_at',
            'revoked_at',
        ]
    
    def get_key_display(self, obj):
        """Return masked key for display."""
        return f"{obj.key_prefix}{'*' * 40}"
    
    def get_is_valid(self, obj):
        """Check if key is valid."""
        return obj.is_valid()
    
    def get_days_until_expiry(self, obj):
        """Get days until key expires."""
        if not obj.expires_at:
            return None
        from django.utils import timezone
        delta = obj.expires_at - timezone.now()
        return delta.days if delta.days > 0 else 0


class APIKeyCreateSerializer(serializers.Serializer):
    """Serializer for creating a new API key."""
    name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Optional name for the key"
    )
    expires_in_days = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        max_value=3650,
        help_text="Number of days until key expires (null = never expires)"
    )
    
    def create(self, validated_data):
        """Create a new API key."""
        client = self.context['client']
        name = validated_data.get('name')
        expires_in_days = validated_data.get('expires_in_days')
        
        api_key, secret_key = APIKey.create_key(
            client=client,
            name=name,
            expires_in_days=expires_in_days
        )
        
        # Log the event
        ClientAuditLog.log_event(
            client=client,
            event_type='key_created',
            performed_by=self.context.get('request').user if 'request' in self.context else None,
            description=f'New API key created: {name or "Unnamed"}',
            metadata={'key_id': api_key.key_id}
        )
        
        # Return both the key object and the secret (only shown once)
        return {
            'api_key': api_key,
            'secret_key': secret_key
        }


class APIClientListSerializer(serializers.ModelSerializer):
    """Serializer for API client list view."""
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_client_type_display', read_only=True)
    is_active = serializers.SerializerMethodField()
    active_keys_count = serializers.SerializerMethodField()
    
    class Meta:
        model = APIClient
        fields = [
            'client_id',
            'client_name',
            'client_type',
            'type_display',
            'owner_username',
            'organization',
            'status',
            'status_display',
            'is_active',
            'active_keys_count',
            'created_at',
            'approved_at',
        ]
        read_only_fields = ['client_id', 'created_at', 'approved_at']
    
    def get_is_active(self, obj):
        """Check if client is active."""
        return obj.is_active()
    
    def get_active_keys_count(self, obj):
        """Get count of active keys."""
        return obj.api_keys.filter(is_active=True).count()


class APIClientDetailSerializer(serializers.ModelSerializer):
    """Serializer for API client detail view."""
    owner = UserSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)
    quota = ClientQuotaSerializer(read_only=True)
    api_keys = APIKeySerializer(many=True, read_only=True)
    is_active = serializers.SerializerMethodField()
    allowed_ips_list = serializers.SerializerMethodField()
    total_requests = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = APIClient
        fields = [
            'client_id',
            'client_name',
            'client_type',
            'owner',
            'organization',
            'status',
            'is_active',
            'created_at',
            'updated_at',
            'approved_at',
            'approved_by',
            'disabled_at',
            'disabled_reason',
            'contact_email',
            'description',
            'metadata',
            'allowed_ips',
            'allowed_ips_list',
            'quota',
            'api_keys',
            'total_requests',
            'success_rate',
        ]
        read_only_fields = [
            'client_id',
            'created_at',
            'updated_at',
            'approved_at',
            'approved_by',
            'disabled_at',
        ]
    
    def get_is_active(self, obj):
        """Check if client is active."""
        return obj.is_active()
    
    def get_allowed_ips_list(self, obj):
        """Get list of allowed IPs."""
        return obj.get_allowed_ips()
    
    def get_total_requests(self, obj):
        """Get total request count."""
        from django.db.models import Sum
        total = obj.usage_metrics.aggregate(
            total=Sum('total_requests')
        )['total'] or 0
        return total
    
    def get_success_rate(self, obj):
        """Get overall success rate."""
        from django.db.models import Sum
        metrics = obj.usage_metrics.aggregate(
            total=Sum('total_requests'),
            successful=Sum('successful_requests')
        )
        total = metrics['total'] or 0
        successful = metrics['successful'] or 0
        if total == 0:
            return 0
        return round((successful / total) * 100, 2)


class APIClientCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new API client."""
    class Meta:
        model = APIClient
        fields = [
            'client_name',
            'client_type',
            'organization',
            'contact_email',
            'description',
            'metadata',
            'allowed_ips',
        ]
    
    def create(self, validated_data):
        """Create a new API client."""
        # Set owner to current user
        validated_data['owner'] = self.context['request'].user
        client = super().create(validated_data)
        
        # Create default quota
        ClientQuota.objects.create(client=client)
        
        # Log creation
        ClientAuditLog.log_event(
            client=client,
            event_type='created',
            performed_by=self.context['request'].user,
            description='Client registered via API'
        )
        
        return client


class APIClientUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating an API client."""
    class Meta:
        model = APIClient
        fields = [
            'client_name',
            'organization',
            'contact_email',
            'description',
            'metadata',
            'allowed_ips',
        ]


class ClientUsageMetricsSerializer(serializers.ModelSerializer):
    """Serializer for ClientUsageMetrics model."""
    success_rate = serializers.SerializerMethodField()
    quota_violation_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = ClientUsageMetrics
        fields = [
            'period_start',
            'period_end',
            'period_type',
            'total_requests',
            'successful_requests',
            'failed_requests',
            'success_rate',
            'data_points_read',
            'data_points_written',
            'avg_response_time',
            'max_response_time',
            'quota_violations',
            'quota_violation_rate',
            'bytes_sent',
            'bytes_received',
            'websocket_connections',
            'websocket_messages',
            'created_at',
        ]
        read_only_fields = '__all__'
    
    def get_success_rate(self, obj):
        """Get success rate percentage."""
        return round(obj.success_rate(), 2)
    
    def get_quota_violation_rate(self, obj):
        """Get quota violation rate."""
        return round(obj.quota_violation_rate(), 2)


class ClientAuditLogSerializer(serializers.ModelSerializer):
    """Serializer for ClientAuditLog model."""
    performed_by_username = serializers.CharField(
        source='performed_by.username',
        read_only=True,
        allow_null=True
    )
    event_type_display = serializers.CharField(
        source='get_event_type_display',
        read_only=True
    )
    
    class Meta:
        model = ClientAuditLog
        fields = [
            'id',
            'event_type',
            'event_type_display',
            'timestamp',
            'performed_by_username',
            'description',
            'metadata',
            'ip_address',
            'user_agent',
        ]
        read_only_fields = '__all__'


class ClientLifecycleActionSerializer(serializers.Serializer):
    """Serializer for client lifecycle actions."""
    action = serializers.ChoiceField(
        choices=['approve', 'activate', 'suspend', 'disable', 'revoke'],
        help_text="Lifecycle action to perform"
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Reason for the action (for suspend/disable/revoke)"
    )
