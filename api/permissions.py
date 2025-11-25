"""
Custom permission classes for Databús API with role-based access control.
"""
from rest_framework import permissions


def get_user_role(user):
    """Helper function to get user role from JWT or Operator model."""
    if not user or not user.is_authenticated:
        return None
    
    # Check if role is in JWT token (from request.auth)
    if hasattr(user, 'operator'):
        return user.operator.role
    elif user.is_staff or user.is_superuser:
        return 'admin'
    
    return 'user'


class IsAuthenticatedOrReadOnly(permissions.BasePermission):
    """
    Allow read access to anyone, but write access only to authenticated users.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Check if object has an owner attribute
        if hasattr(obj, 'operator'):
            return obj.operator == request.user.operator
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False


class IsOperatorOrReadOnly(permissions.BasePermission):
    """
    Allow operators to create/update their own data.
    Read-only access for everyone else.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if not request.user or not request.user.is_authenticated:
            return False
        
        role = get_user_role(request.user)
        return role in ['admin', 'operator', 'dispatcher', 'supervisor']


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Allow only admin users to write, anyone can read.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if not request.user or not request.user.is_authenticated:
            return False
        
        role = get_user_role(request.user)
        return role == 'admin' or request.user.is_staff


class IsAdminUser(permissions.BasePermission):
    """
    Allow only admin users (read and write).
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        role = get_user_role(request.user)
        return role == 'admin' or request.user.is_staff


class IsSupervisorOrAdmin(permissions.BasePermission):
    """
    Allow supervisors and admins full access.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        role = get_user_role(request.user)
        return role in ['admin', 'supervisor'] or request.user.is_staff


class CanManageEquipment(permissions.BasePermission):
    """
    Allow users to manage equipment (devices) for their company.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        if not request.user or not request.user.is_authenticated:
            return False
        
        role = get_user_role(request.user)
        return role in ['admin', 'supervisor', 'dispatcher'] or request.user.is_staff
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Staff can manage all equipment
        if request.user.is_staff:
            return True
        
        role = get_user_role(request.user)
        
        # Admins can manage all
        if role == 'admin':
            return True
        
        # Others can only manage their company's equipment
        if hasattr(request.user, 'operator'):
            user_companies = request.user.operator.company.all()
            return obj.vehicle.company in user_companies
        
        return False


class IsReadOnly(permissions.BasePermission):
    """
    Read-only permission for readonly role users.
    """
    
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS
