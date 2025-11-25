"""
ViewSets for API Client Registry and Lifecycle Management.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .client_models import (
    APIClient,
    APIKey,
    ClientQuota,
    ClientUsageMetrics,
    ClientAuditLog,
)
from .client_serializers import (
    APIClientListSerializer,
    APIClientDetailSerializer,
    APIClientCreateSerializer,
    APIClientUpdateSerializer,
    APIKeySerializer,
    APIKeyCreateSerializer,
    ClientQuotaSerializer,
    ClientUsageMetricsSerializer,
    ClientAuditLogSerializer,
    ClientLifecycleActionSerializer,
)
from .permissions import IsAdminOrReadOnly, IsOwnerOrReadOnly


class APIClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing API clients.
    
    Provides full CRUD operations and lifecycle management for API clients.
    Users can only see and manage their own clients unless they are admins.
    """
    queryset = APIClient.objects.all().select_related(
        'owner', 'approved_by'
    ).prefetch_related(
        'api_keys', 'quota', 'usage_metrics'
    )
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    lookup_field = 'client_id'
    
    def get_serializer_class(self):
        """Return appropriate serializer class based on action."""
        if self.action == 'list':
            return APIClientListSerializer
        elif self.action == 'create':
            return APIClientCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return APIClientUpdateSerializer
        return APIClientDetailSerializer
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        user = self.request.user
        if user.is_staff or (hasattr(user, 'operator') and user.operator.is_admin):
            return self.queryset
        return self.queryset.filter(owner=user)
    
    @extend_schema(
        summary="List API clients",
        description="Get a list of all API clients owned by the current user (or all clients for admins).",
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                enum=['pending', 'active', 'suspended', 'disabled', 'revoked'],
                description='Filter by client status'
            ),
            OpenApiParameter(
                name='client_type',
                type=OpenApiTypes.STR,
                enum=['vehicle', 'device', 'user', 'agency', 'integration'],
                description='Filter by client type'
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        """List API clients with optional filtering."""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        type_filter = request.query_params.get('client_type')
        if type_filter:
            queryset = queryset.filter(client_type=type_filter)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Create API client",
        description="Register a new API client. The client will be in 'pending' status until approved by an admin.",
        examples=[
            OpenApiExample(
                'Create Vehicle Client',
                value={
                    'client_name': 'Bus 101 GPS Device',
                    'client_type': 'vehicle',
                    'organization': 'Transit Company A',
                    'contact_email': 'tech@transit-a.com',
                    'description': 'GPS device for bus 101',
                    'metadata': {'vehicle_id': 'BUS-101', 'device_serial': 'GPS123456'}
                }
            ),
        ]
    )
    def create(self, request, *args, **kwargs):
        """Create a new API client."""
        return super().create(request, *args, **kwargs)
    
    @extend_schema(
        summary="Get API client details",
        description="Get detailed information about a specific API client, including quota and API keys."
    )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve API client details."""
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Update API client",
        description="Update an API client's information (owner or admin only)."
    )
    def update(self, request, *args, **kwargs):
        """Update API client."""
        return super().update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Delete API client",
        description="Delete an API client (admin only). This will revoke all associated API keys."
    )
    def destroy(self, request, *args, **kwargs):
        """Delete API client."""
        instance = self.get_object()
        
        # Log deletion
        ClientAuditLog.log_event(
            client=instance,
            event_type='revoked',
            performed_by=request.user,
            description=f'Client deleted by {request.user.username}'
        )
        
        return super().destroy(request, *args, **kwargs)
    
    @extend_schema(
        summary="Perform lifecycle action",
        description="Perform a lifecycle action on the client (approve, activate, suspend, disable, revoke).",
        request=ClientLifecycleActionSerializer,
        examples=[
            OpenApiExample(
                'Approve client',
                value={'action': 'approve'}
            ),
            OpenApiExample(
                'Suspend client',
                value={'action': 'suspend', 'reason': 'Suspicious activity detected'}
            ),
        ]
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrReadOnly])
    def lifecycle(self, request, client_id=None):
        """Perform lifecycle action on client."""
        client = self.get_object()
        serializer = ClientLifecycleActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        action_type = serializer.validated_data['action']
        reason = serializer.validated_data.get('reason', '')
        
        if action_type == 'approve':
            if client.status != 'pending':
                return Response(
                    {'error': 'Only pending clients can be approved'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            client.activate(approved_by=request.user)
            ClientAuditLog.log_event(
                client=client,
                event_type='approved',
                performed_by=request.user,
                description=f'Client approved by {request.user.username}'
            )
        
        elif action_type == 'activate':
            if client.status in ['active', 'revoked']:
                return Response(
                    {'error': f'Cannot activate {client.status} client'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            client.activate(approved_by=request.user)
            ClientAuditLog.log_event(
                client=client,
                event_type='activated',
                performed_by=request.user,
                description=f'Client activated by {request.user.username}'
            )
        
        elif action_type == 'suspend':
            if client.status != 'active':
                return Response(
                    {'error': 'Only active clients can be suspended'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            client.suspend(reason=reason)
            ClientAuditLog.log_event(
                client=client,
                event_type='suspended',
                performed_by=request.user,
                description=f'Client suspended by {request.user.username}. Reason: {reason}'
            )
        
        elif action_type == 'disable':
            client.disable(reason=reason)
            ClientAuditLog.log_event(
                client=client,
                event_type='disabled',
                performed_by=request.user,
                description=f'Client disabled by {request.user.username}. Reason: {reason}'
            )
        
        elif action_type == 'revoke':
            client.revoke(reason=reason)
            ClientAuditLog.log_event(
                client=client,
                event_type='revoked',
                performed_by=request.user,
                description=f'Client revoked by {request.user.username}. Reason: {reason}'
            )
        
        serializer = self.get_serializer(client)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get client quota",
        description="Get the quota and limits for this client."
    )
    @action(detail=True, methods=['get'])
    def quota(self, request, client_id=None):
        """Get client quota."""
        client = self.get_object()
        quota = client.quota
        serializer = ClientQuotaSerializer(quota)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Update client quota",
        description="Update the quota and limits for this client (admin only).",
        request=ClientQuotaSerializer
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, IsAdminOrReadOnly])
    def update_quota(self, request, client_id=None):
        """Update client quota."""
        client = self.get_object()
        quota = client.quota
        serializer = ClientQuotaSerializer(quota, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        ClientAuditLog.log_event(
            client=client,
            event_type='quota_updated',
            performed_by=request.user,
            description=f'Quota updated by {request.user.username}',
            metadata={'limits': quota.get_limits()}
        )
        
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get usage metrics",
        description="Get usage metrics for this client.",
        parameters=[
            OpenApiParameter(
                name='period_type',
                type=OpenApiTypes.STR,
                enum=['hour', 'day', 'month'],
                description='Filter by period type'
            ),
            OpenApiParameter(
                name='days',
                type=OpenApiTypes.INT,
                description='Number of days to look back (default: 7)'
            ),
        ]
    )
    @action(detail=True, methods=['get'])
    def metrics(self, request, client_id=None):
        """Get usage metrics for client."""
        client = self.get_object()
        
        # Get parameters
        period_type = request.query_params.get('period_type', 'day')
        days = int(request.query_params.get('days', 7))
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timezone.timedelta(days=days)
        
        # Query metrics
        metrics = client.usage_metrics.filter(
            period_type=period_type,
            period_start__gte=start_date,
            period_start__lte=end_date
        ).order_by('-period_start')
        
        serializer = ClientUsageMetricsSerializer(metrics, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get audit log",
        description="Get audit log entries for this client.",
        parameters=[
            OpenApiParameter(
                name='event_type',
                type=OpenApiTypes.STR,
                description='Filter by event type'
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                description='Limit number of results (default: 50)'
            ),
        ]
    )
    @action(detail=True, methods=['get'])
    def audit_log(self, request, client_id=None):
        """Get audit log for client."""
        client = self.get_object()
        
        # Get parameters
        event_type = request.query_params.get('event_type')
        limit = int(request.query_params.get('limit', 50))
        
        # Query audit logs
        logs = client.audit_logs.all()
        if event_type:
            logs = logs.filter(event_type=event_type)
        
        logs = logs[:limit]
        
        serializer = ClientAuditLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Create API key",
        description="Create a new API key for this client.",
        request=APIKeyCreateSerializer,
        examples=[
            OpenApiExample(
                'Create permanent key',
                value={'name': 'Production Key'}
            ),
            OpenApiExample(
                'Create temporary key',
                value={'name': 'Testing Key', 'expires_in_days': 30}
            ),
        ]
    )
    @action(detail=True, methods=['post'])
    def create_key(self, request, client_id=None):
        """Create a new API key for this client."""
        client = self.get_object()
        
        serializer = APIKeyCreateSerializer(
            data=request.data,
            context={'client': client, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        
        api_key = result['api_key']
        secret_key = result['secret_key']
        
        return Response({
            'message': 'API key created successfully. Save the secret key securely - it will not be shown again.',
            'key': APIKeySerializer(api_key).data,
            'secret_key': secret_key,
        }, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="List API keys",
        description="List all API keys for this client."
    )
    @action(detail=True, methods=['get'])
    def keys(self, request, client_id=None):
        """List API keys for this client."""
        client = self.get_object()
        keys = client.api_keys.all().order_by('-created_at')
        serializer = APIKeySerializer(keys, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Revoke API key",
        description="Revoke a specific API key.",
        parameters=[
            OpenApiParameter(
                name='key_id',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='API key ID to revoke'
            ),
        ]
    )
    @action(detail=True, methods=['post'], url_path='keys/(?P<key_id>[^/.]+)/revoke')
    def revoke_key(self, request, client_id=None, key_id=None):
        """Revoke an API key."""
        client = self.get_object()
        
        try:
            api_key = client.api_keys.get(key_id=key_id)
        except APIKey.DoesNotExist:
            return Response(
                {'error': 'API key not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not api_key.is_active:
            return Response(
                {'error': 'API key is already revoked'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        api_key.revoke()
        
        ClientAuditLog.log_event(
            client=client,
            event_type='key_revoked',
            performed_by=request.user,
            description=f'API key {api_key.key_prefix}... revoked by {request.user.username}',
            metadata={'key_id': api_key.key_id}
        )
        
        return Response({
            'message': 'API key revoked successfully',
            'key': APIKeySerializer(api_key).data
        })
    
    @extend_schema(
        summary="Rotate API key",
        description="Rotate an API key (create new one and revoke old one).",
        parameters=[
            OpenApiParameter(
                name='key_id',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='API key ID to rotate'
            ),
        ],
        request=APIKeyCreateSerializer
    )
    @action(detail=True, methods=['post'], url_path='keys/(?P<key_id>[^/.]+)/rotate')
    def rotate_key(self, request, client_id=None, key_id=None):
        """Rotate an API key."""
        client = self.get_object()
        
        try:
            old_key = client.api_keys.get(key_id=key_id)
        except APIKey.DoesNotExist:
            return Response(
                {'error': 'API key not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not old_key.is_active:
            return Response(
                {'error': 'Cannot rotate inactive key'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get expiry from request data
        serializer = APIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expires_in_days = serializer.validated_data.get('expires_in_days')
        
        # Rotate the key
        new_key, secret_key = old_key.rotate(expires_in_days=expires_in_days)
        
        ClientAuditLog.log_event(
            client=client,
            event_type='key_rotated',
            performed_by=request.user,
            description=f'API key rotated by {request.user.username}',
            metadata={
                'old_key_id': old_key.key_id,
                'new_key_id': new_key.key_id
            }
        )
        
        return Response({
            'message': 'API key rotated successfully. Save the new secret key securely.',
            'old_key': APIKeySerializer(old_key).data,
            'new_key': APIKeySerializer(new_key).data,
            'secret_key': secret_key,
        })


class ClientUsageMetricsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing usage metrics (read-only).
    """
    queryset = ClientUsageMetrics.objects.all().select_related('client')
    serializer_class = ClientUsageMetricsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter metrics based on user permissions."""
        user = self.request.user
        if user.is_staff or (hasattr(user, 'operator') and user.operator.is_admin):
            return self.queryset
        return self.queryset.filter(client__owner=user)


class ClientAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing audit logs (read-only).
    """
    queryset = ClientAuditLog.objects.all().select_related('client', 'performed_by')
    serializer_class = ClientAuditLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter audit logs based on user permissions."""
        user = self.request.user
        if user.is_staff or (hasattr(user, 'operator') and user.operator.is_admin):
            return self.queryset
        return self.queryset.filter(client__owner=user)
