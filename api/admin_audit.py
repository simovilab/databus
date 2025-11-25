"""
Admin Audit Middleware

Automatically logs administrative actions performed in the Django admin interface.
Captures user actions, IP addresses, and change details for compliance and security.
"""
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.contenttypes.models import ContentType
from django.utils.deprecation import MiddlewareMixin
from api.models import AdminAuditLog


class AdminAuditMiddleware(MiddlewareMixin):
    """
    Middleware to capture and log admin panel actions.
    
    Monitors all admin actions and creates detailed audit logs including:
    - User who performed the action
    - Type of action (view, add, change, delete)
    - Object affected
    - IP address and user agent
    - Before/after values for changes
    """
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Capture admin view access.
        """
        # Only monitor admin views
        if not request.path.startswith('/admin/'):
            return None
        
        # Store request context for later use
        request._admin_audit_context = {
            'ip_address': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
        }
        
        return None
    
    def process_response(self, request, response):
        """
        Log admin actions after response is generated.
        """
        # Only process admin requests with authenticated users
        if not request.path.startswith('/admin/') or not request.user.is_authenticated:
            return response
        
        # Log view access for change/changelist views
        if hasattr(request, '_admin_audit_context'):
            self._log_view_access(request, response)
        
        return response
    
    def _log_view_access(self, request, response):
        """Log read-only view access to admin panels."""
        # Only log successful GET requests (viewing data)
        if request.method != 'GET' or response.status_code >= 400:
            return
        
        path_parts = request.path.strip('/').split('/')
        
        # Check if this is a changelist or change view
        if len(path_parts) >= 4 and path_parts[0] == 'admin':
            app_label = path_parts[1]
            model_name = path_parts[2]
            
            # Skip logging for certain admin views
            if model_name in ['jsi18n', 'autocomplete']:
                return
            
            context = request._admin_audit_context
            
            # Determine if it's a list view or detail view
            if len(path_parts) == 4 and path_parts[3] == 'change':
                # Changelist view
                AdminAuditLog.log_action(
                    action_type='view',
                    content_type=f'{app_label}.{model_name}',
                    object_repr=f'{model_name.title()} List',
                    user=request.user,
                    ip_address=context['ip_address'],
                    user_agent=context['user_agent'],
                    notes='Viewed changelist'
                )
            elif len(path_parts) >= 5:
                # Detail view
                object_id = path_parts[3]
                AdminAuditLog.log_action(
                    action_type='view',
                    content_type=f'{app_label}.{model_name}',
                    object_id=object_id,
                    object_repr=f'{model_name.title()} #{object_id}',
                    user=request.user,
                    ip_address=context['ip_address'],
                    user_agent=context['user_agent'],
                    notes='Viewed object details'
                )
    
    @staticmethod
    def _get_client_ip(request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


def log_admin_action(modeladmin, request, queryset, action_name):
    """
    Helper function to log bulk admin actions.
    
    Usage in ModelAdmin:
        actions = ['my_custom_action']
        
        def my_custom_action(self, request, queryset):
            # Perform action
            log_admin_action(self, request, queryset, 'custom_action')
            self.message_user(request, f"Action completed on {queryset.count()} items")
    
    Args:
        modeladmin: The ModelAdmin instance
        request: The current request
        queryset: The selected objects
        action_name: Name of the action performed
    """
    ip_address = AdminAuditMiddleware._get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    
    model_name = queryset.model._meta.model_name
    app_label = queryset.model._meta.app_label
    
    AdminAuditLog.log_action(
        action_type='bulk_action',
        content_type=f'{app_label}.{model_name}',
        object_repr=f'Bulk {action_name} on {queryset.count()} {model_name}(s)',
        user=request.user,
        ip_address=ip_address,
        user_agent=user_agent,
        changes={'action': action_name, 'count': queryset.count()},
        notes=f'Bulk action: {action_name}'
    )


def log_model_change(obj, action_type, user, request, changes=None):
    """
    Helper function to log model changes from ModelAdmin.
    
    Usage in ModelAdmin:
        def save_model(self, request, obj, form, change):
            super().save_model(request, obj, form, change)
            action = 'change' if change else 'add'
            changes = {}
            if change:
                changes = {field: (form.initial.get(field), form.cleaned_data.get(field))
                          for field in form.changed_data}
            log_model_change(obj, action, request.user, request, changes)
    
    Args:
        obj: The model instance
        action_type: 'add', 'change', or 'delete'
        user: The user performing the action
        request: The current request
        changes: Dictionary of changed fields with before/after values
    """
    ip_address = AdminAuditMiddleware._get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    
    model_name = obj._meta.model_name
    app_label = obj._meta.app_label
    
    AdminAuditLog.log_action(
        action_type=action_type,
        content_type=f'{app_label}.{model_name}',
        object_id=obj.pk,
        object_repr=str(obj),
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        changes=changes or {},
        notes=f'{action_type.title()} operation on {model_name}'
    )
