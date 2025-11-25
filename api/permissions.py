"""
Custom permission classes for Databús API.
"""
from rest_framework import permissions


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
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return (
            request.user 
            and request.user.is_authenticated 
            and hasattr(request.user, 'operator')
        )


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Allow only admin users to write, anyone can read.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return request.user and request.user.is_staff


class IsAdminUser(permissions.BasePermission):
    """
    Allow only admin users (read and write).
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class CanManageEquipment(permissions.BasePermission):
    """
    Allow users to manage equipment (devices) for their company.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        return (
            request.user 
            and request.user.is_authenticated 
            and (request.user.is_staff or hasattr(request.user, 'operator'))
        )
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Staff can manage all equipment
        if request.user.is_staff:
            return True
        
        # Operators can only manage their company's equipment
        if hasattr(request.user, 'operator'):
            user_companies = request.user.operator.company.all()
            return obj.vehicle.company in user_companies
        
        return False
