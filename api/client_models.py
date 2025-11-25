"""
API Client Registry and Lifecycle Management Models.

This module provides models for managing API clients (vehicles, devices, users, agencies)
with authentication keys, usage quotas, status tracking, and metrics.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
from datetime import timedelta
import secrets
import hashlib


class ClientType(models.TextChoices):
    """Types of API clients."""
    VEHICLE = 'vehicle', 'Vehicle Device'
    DEVICE = 'device', 'Generic Device'
    USER = 'user', 'User Application'
    AGENCY = 'agency', 'Agency System'
    INTEGRATION = 'integration', 'Third-party Integration'


class ClientStatus(models.TextChoices):
    """Status of API client."""
    PENDING = 'pending', 'Pending Approval'
    ACTIVE = 'active', 'Active'
    SUSPENDED = 'suspended', 'Suspended'
    DISABLED = 'disabled', 'Disabled'
    REVOKED = 'revoked', 'Revoked'


class APIClient(models.Model):
    """
    Represents a registered API client with authentication and quota management.
    """
    # Identification
    client_id = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        help_text="Unique client identifier"
    )
    client_name = models.CharField(
        max_length=255,
        help_text="Descriptive name for the client"
    )
    client_type = models.CharField(
        max_length=20,
        choices=ClientType.choices,
        default=ClientType.DEVICE,
        help_text="Type of client"
    )
    
    # Ownership
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='api_clients',
        help_text="User who owns this client"
    )
    organization = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Organization name if applicable"
    )
    
    # Status and lifecycle
    status = models.CharField(
        max_length=20,
        choices=ClientStatus.choices,
        default=ClientStatus.PENDING,
        help_text="Current status of the client"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the client was approved"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_clients',
        help_text="Admin who approved this client"
    )
    disabled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the client was disabled"
    )
    disabled_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for disabling the client"
    )
    
    # Contact and metadata
    contact_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Contact email for this client"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description of the client's purpose"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (vehicle ID, device serial, etc.)"
    )
    
    # IP whitelist
    allowed_ips = models.TextField(
        blank=True,
        null=True,
        help_text="Comma-separated list of allowed IP addresses (optional)"
    )
    
    class Meta:
        db_table = 'api_client'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['owner', 'status']),
        ]
    
    def __str__(self):
        return f"{self.client_name} ({self.client_id})"
    
    def save(self, *args, **kwargs):
        if not self.client_id:
            self.client_id = self.generate_client_id()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_client_id():
        """Generate a unique client ID."""
        return f"client_{secrets.token_urlsafe(32)}"
    
    def is_active(self):
        """Check if client is active."""
        return self.status == ClientStatus.ACTIVE
    
    def activate(self, approved_by=None):
        """Activate the client."""
        self.status = ClientStatus.ACTIVE
        self.approved_at = timezone.now()
        self.approved_by = approved_by
        self.save()
    
    def suspend(self, reason=None):
        """Suspend the client."""
        self.status = ClientStatus.SUSPENDED
        self.disabled_reason = reason
        self.disabled_at = timezone.now()
        self.save()
    
    def disable(self, reason=None):
        """Disable the client."""
        self.status = ClientStatus.DISABLED
        self.disabled_reason = reason
        self.disabled_at = timezone.now()
        self.save()
    
    def revoke(self, reason=None):
        """Revoke the client permanently."""
        self.status = ClientStatus.REVOKED
        self.disabled_reason = reason
        self.disabled_at = timezone.now()
        self.save()
        # Revoke all API keys
        self.api_keys.update(is_active=False, revoked_at=timezone.now())
    
    def get_allowed_ips(self):
        """Get list of allowed IPs."""
        if not self.allowed_ips:
            return []
        return [ip.strip() for ip in self.allowed_ips.split(',') if ip.strip()]
    
    def check_ip_allowed(self, ip_address):
        """Check if an IP address is allowed."""
        allowed = self.get_allowed_ips()
        if not allowed:
            return True  # No restriction
        return ip_address in allowed


class APIKey(models.Model):
    """
    API keys for client authentication.
    Supports key rotation and lifecycle management.
    """
    # Key identification
    key_id = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        help_text="Public key identifier"
    )
    key_hash = models.CharField(
        max_length=128,
        editable=False,
        help_text="Hashed secret key"
    )
    key_prefix = models.CharField(
        max_length=8,
        editable=False,
        help_text="Key prefix for identification"
    )
    
    # Association
    client = models.ForeignKey(
        APIClient,
        on_delete=models.CASCADE,
        related_name='api_keys',
        help_text="Associated API client"
    )
    
    # Lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the key expires (null = never)"
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this key was used"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the key is active"
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the key was revoked"
    )
    
    # Metadata
    name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Optional name for the key"
    )
    
    class Meta:
        db_table = 'api_key'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['key_id']),
            models.Index(fields=['client', 'is_active']),
            models.Index(fields=['key_hash']),
        ]
    
    def __str__(self):
        return f"{self.key_prefix}... ({self.client.client_name})"
    
    @staticmethod
    def generate_key():
        """Generate a new API key and return (key_id, secret_key, key_hash)."""
        key_id = f"key_{secrets.token_urlsafe(16)}"
        secret_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(secret_key.encode()).hexdigest()
        key_prefix = secret_key[:8]
        return key_id, secret_key, key_hash, key_prefix
    
    @classmethod
    def create_key(cls, client, name=None, expires_in_days=None):
        """Create a new API key for a client."""
        key_id, secret_key, key_hash, key_prefix = cls.generate_key()
        
        expires_at = None
        if expires_in_days:
            expires_at = timezone.now() + timedelta(days=expires_in_days)
        
        api_key = cls.objects.create(
            key_id=key_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            client=client,
            name=name,
            expires_at=expires_at
        )
        
        # Return the secret key only once
        return api_key, secret_key
    
    @staticmethod
    def hash_key(secret_key):
        """Hash a secret key."""
        return hashlib.sha256(secret_key.encode()).hexdigest()
    
    def verify_key(self, secret_key):
        """Verify if a secret key matches this API key."""
        return self.key_hash == self.hash_key(secret_key)
    
    def is_valid(self):
        """Check if the key is valid (active and not expired)."""
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True
    
    def revoke(self):
        """Revoke this API key."""
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save()
    
    def rotate(self, expires_in_days=None):
        """Rotate this key (create new one and revoke this one)."""
        new_key, secret_key = APIKey.create_key(
            client=self.client,
            name=f"{self.name} (rotated)" if self.name else "Rotated key",
            expires_in_days=expires_in_days
        )
        self.revoke()
        return new_key, secret_key
    
    def record_usage(self):
        """Record that this key was just used."""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])


class ClientQuota(models.Model):
    """
    Usage quotas and limits for API clients.
    """
    client = models.OneToOneField(
        APIClient,
        on_delete=models.CASCADE,
        related_name='quota',
        primary_key=True
    )
    
    # Rate limits
    requests_per_minute = models.IntegerField(
        default=60,
        validators=[MinValueValidator(1)],
        help_text="Maximum requests per minute"
    )
    requests_per_hour = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(1)],
        help_text="Maximum requests per hour"
    )
    requests_per_day = models.IntegerField(
        default=10000,
        validators=[MinValueValidator(1)],
        help_text="Maximum requests per day"
    )
    
    # Data limits
    max_data_points_per_request = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(1)],
        help_text="Maximum data points per request"
    )
    max_concurrent_connections = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1)],
        help_text="Maximum concurrent WebSocket connections"
    )
    
    # Features
    can_write = models.BooleanField(
        default=False,
        help_text="Can write data via API"
    )
    can_subscribe_realtime = models.BooleanField(
        default=True,
        help_text="Can subscribe to real-time updates"
    )
    can_access_historical = models.BooleanField(
        default=True,
        help_text="Can access historical data"
    )
    
    # Soft limits
    warning_threshold = models.FloatField(
        default=0.8,
        validators=[MinValueValidator(0), MinValueValidator(1)],
        help_text="Threshold (0-1) for quota warnings"
    )
    
    class Meta:
        db_table = 'api_client_quota'
    
    def __str__(self):
        return f"Quota for {self.client.client_name}"
    
    def get_limits(self):
        """Get all limits as a dictionary."""
        return {
            'requests_per_minute': self.requests_per_minute,
            'requests_per_hour': self.requests_per_hour,
            'requests_per_day': self.requests_per_day,
            'max_data_points_per_request': self.max_data_points_per_request,
            'max_concurrent_connections': self.max_concurrent_connections,
        }


class ClientUsageMetrics(models.Model):
    """
    Track usage metrics for API clients.
    Records are created periodically (hourly/daily).
    """
    client = models.ForeignKey(
        APIClient,
        on_delete=models.CASCADE,
        related_name='usage_metrics'
    )
    
    # Time period
    period_start = models.DateTimeField(
        help_text="Start of the measurement period"
    )
    period_end = models.DateTimeField(
        help_text="End of the measurement period"
    )
    period_type = models.CharField(
        max_length=10,
        choices=[
            ('hour', 'Hourly'),
            ('day', 'Daily'),
            ('month', 'Monthly'),
        ],
        default='hour'
    )
    
    # Request metrics
    total_requests = models.IntegerField(
        default=0,
        help_text="Total number of requests"
    )
    successful_requests = models.IntegerField(
        default=0,
        help_text="Number of successful requests (2xx)"
    )
    failed_requests = models.IntegerField(
        default=0,
        help_text="Number of failed requests (4xx, 5xx)"
    )
    
    # Data metrics
    data_points_read = models.IntegerField(
        default=0,
        help_text="Number of data points read"
    )
    data_points_written = models.IntegerField(
        default=0,
        help_text="Number of data points written"
    )
    
    # Response time metrics (in milliseconds)
    avg_response_time = models.FloatField(
        default=0,
        help_text="Average response time in ms"
    )
    max_response_time = models.FloatField(
        default=0,
        help_text="Maximum response time in ms"
    )
    
    # Quota violations
    quota_violations = models.IntegerField(
        default=0,
        help_text="Number of quota violation events"
    )
    
    # Bandwidth (bytes)
    bytes_sent = models.BigIntegerField(
        default=0,
        help_text="Total bytes sent to client"
    )
    bytes_received = models.BigIntegerField(
        default=0,
        help_text="Total bytes received from client"
    )
    
    # WebSocket metrics
    websocket_connections = models.IntegerField(
        default=0,
        help_text="Number of WebSocket connections opened"
    )
    websocket_messages = models.IntegerField(
        default=0,
        help_text="Number of WebSocket messages sent"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'api_client_usage_metrics'
        ordering = ['-period_start']
        unique_together = [['client', 'period_start', 'period_type']]
        indexes = [
            models.Index(fields=['client', '-period_start']),
            models.Index(fields=['period_type', '-period_start']),
        ]
    
    def __str__(self):
        return f"{self.client.client_name} - {self.period_start.date()} ({self.period_type})"
    
    def success_rate(self):
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 0
        return (self.successful_requests / self.total_requests) * 100
    
    def quota_violation_rate(self):
        """Calculate quota violation rate."""
        if self.total_requests == 0:
            return 0
        return (self.quota_violations / self.total_requests) * 100


class ClientAuditLog(models.Model):
    """
    Audit log for client lifecycle events and administrative actions.
    """
    client = models.ForeignKey(
        APIClient,
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    
    # Event details
    event_type = models.CharField(
        max_length=50,
        choices=[
            ('created', 'Client Created'),
            ('approved', 'Client Approved'),
            ('activated', 'Client Activated'),
            ('suspended', 'Client Suspended'),
            ('disabled', 'Client Disabled'),
            ('revoked', 'Client Revoked'),
            ('key_created', 'API Key Created'),
            ('key_rotated', 'API Key Rotated'),
            ('key_revoked', 'API Key Revoked'),
            ('quota_updated', 'Quota Updated'),
            ('quota_exceeded', 'Quota Exceeded'),
            ('ip_blocked', 'IP Address Blocked'),
        ],
        help_text="Type of event"
    )
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Actor (who performed the action)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_audit_actions',
        help_text="User who performed the action (null for system actions)"
    )
    
    # Event details
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Detailed description of the event"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional event metadata"
    )
    
    # Context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address associated with the event"
    )
    user_agent = models.TextField(
        blank=True,
        null=True,
        help_text="User agent string"
    )
    
    class Meta:
        db_table = 'api_client_audit_log'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['client', '-timestamp']),
            models.Index(fields=['event_type', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.client.client_name} - {self.event_type} at {self.timestamp}"
    
    @classmethod
    def log_event(cls, client, event_type, performed_by=None, description=None, 
                  metadata=None, ip_address=None, user_agent=None):
        """Helper method to create an audit log entry."""
        return cls.objects.create(
            client=client,
            event_type=event_type,
            performed_by=performed_by,
            description=description,
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent
        )


class AdminAuditLog(models.Model):
    """
    Audit log for administrative actions in the admin panel.
    
    Tracks all administrative operations including views, changes, and deletions
    for compliance and security monitoring.
    """
    
    # Action details
    action_type = models.CharField(
        max_length=50,
        choices=[
            ('view', 'Viewed'),
            ('add', 'Added'),
            ('change', 'Changed'),
            ('delete', 'Deleted'),
            ('export', 'Exported'),
            ('bulk_action', 'Bulk Action'),
            ('login', 'Admin Login'),
            ('logout', 'Admin Logout'),
            ('permission_change', 'Permission Changed'),
        ],
        help_text="Type of administrative action"
    )
    
    # Target information
    content_type = models.CharField(
        max_length=100,
        help_text="Type of object affected (e.g., 'apiclient', 'apikey')"
    )
    object_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="ID of the affected object"
    )
    object_repr = models.CharField(
        max_length=500,
        help_text="String representation of the affected object"
    )
    
    # Timing
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Actor
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='admin_audit_logs',
        help_text="Admin user who performed the action"
    )
    
    # Context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the admin user"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="Browser user agent string"
    )
    
    # Change details
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Details of what was changed (before/after values)"
    )
    
    # Additional context
    notes = models.TextField(
        blank=True,
        help_text="Additional notes or reason for the action"
    )
    
    class Meta:
        db_table = 'api_admin_audit_log'
        ordering = ['-timestamp']
        verbose_name = 'Admin Audit Log'
        verbose_name_plural = 'Admin Audit Logs'
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action_type', '-timestamp']),
            models.Index(fields=['content_type', '-timestamp']),
        ]
    
    def __str__(self):
        action = self.get_action_type_display()
        user = self.user.username if self.user else 'System'
        return f"{user} {action} {self.content_type} at {self.timestamp}"
    
    @classmethod
    def log_action(cls, action_type, content_type, object_repr, user=None,
                   object_id=None, ip_address=None, user_agent=None, 
                   changes=None, notes=''):
        """
        Helper method to create an admin audit log entry.
        
        Args:
            action_type: Type of action (view, add, change, delete, etc.)
            content_type: Type of object affected
            object_repr: String representation of the object
            user: User who performed the action
            object_id: ID of the affected object
            ip_address: IP address of the user
            user_agent: Browser user agent
            changes: Dictionary of changes (before/after values)
            notes: Additional notes
        
        Returns:
            AdminAuditLog instance
        """
        return cls.objects.create(
            action_type=action_type,
            content_type=content_type,
            object_id=str(object_id) if object_id else None,
            object_repr=object_repr[:500],  # Truncate if too long
            user=user,
            ip_address=ip_address,
            user_agent=user_agent or '',  # Default to empty string
            changes=changes or {},
            notes=notes
        )
