"""
Custom permissions for Stock Management System API.
"""
from rest_framework import permissions
from apps.users.models import UserRole


class IsAdmin(permissions.BasePermission):
    """
    Permission that only allows administrators.
    """
    
    def has_permission(self, request, view):
        """Check if user is an administrator."""
        return (
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'profile') and
            request.user.profile.role == UserRole.ADMIN
        )


class IsTechnician(permissions.BasePermission):
    """
    Permission that only allows technicians.
    """
    
    def has_permission(self, request, view):
        """Check if user is a technician."""
        return (
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'profile') and
            request.user.profile.role == UserRole.TECH
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission that allows access to object owners or administrators.
    """
    
    def has_permission(self, request, view):
        """Check if user is authenticated."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user is owner or admin."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        if not hasattr(request.user, 'profile'):
            return False
        
        # Admins can access everything
        if request.user.profile.role == UserRole.ADMIN:
            return True
        
        # Check if user is the owner of the object
        # This assumes the object has a 'technician' field that links to a Profile
        if hasattr(obj, 'technician'):
            return obj.technician == request.user.profile
        
        # Check if user is the owner via 'user' field
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check if object has a 'panier' field with technician
        if hasattr(obj, 'panier') and hasattr(obj.panier, 'technician'):
            return obj.panier.technician == request.user.profile
        
        # Check if object has a 'demande' field with technician
        if hasattr(obj, 'demande') and hasattr(obj.demande, 'technician'):
            return obj.demande.technician == request.user.profile
        
        return False


class IsTechnicianOrAdmin(permissions.BasePermission):
    """
    Permission that allows access to technicians or administrators.
    """
    
    def has_permission(self, request, view):
        """Check if user is technician or admin."""
        return (
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'profile') and
            request.user.profile.role in [UserRole.TECH, UserRole.ADMIN]
        )


class IsTechnicianOwnerOrAdmin(permissions.BasePermission):
    """
    Permission for technician-specific resources.
    Technicians can only access their own resources, admins can access all.
    """
    
    def has_permission(self, request, view):
        """Check if user is authenticated and has appropriate role."""
        return (
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'profile') and
            request.user.profile.role in [UserRole.TECH, UserRole.ADMIN]
        )
    
    def has_object_permission(self, request, view, obj):
        """Check object-level permissions."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        if not hasattr(request.user, 'profile'):
            return False
        
        # Admins can access everything
        if request.user.profile.role == UserRole.ADMIN:
            return True
        
        # Technicians can only access their own resources
        if request.user.profile.role == UserRole.TECH:
            # Check various ways the object might be linked to the technician
            if hasattr(obj, 'technician'):
                return obj.technician == request.user.profile
            elif hasattr(obj, 'panier') and hasattr(obj.panier, 'technician'):
                return obj.panier.technician == request.user.profile
            elif hasattr(obj, 'demande') and hasattr(obj.demande, 'technician'):
                return obj.demande.technician == request.user.profile
            elif hasattr(obj, 'user'):
                return obj.user == request.user
        
        return False


class ReadOnlyOrAdmin(permissions.BasePermission):
    """
    Permission that allows read-only access to all authenticated users,
    but write access only to administrators.
    """
    
    def has_permission(self, request, view):
        """Check permissions based on request method."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        if not hasattr(request.user, 'profile'):
            return False
        
        # Read permissions for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for admins
        return request.user.profile.role == UserRole.ADMIN


class ArticlePermissions(permissions.BasePermission):
    """
    Custom permissions for Article management.
    - Technicians: read-only access to active articles
    - Admins: full access to all articles
    """
    
    def has_permission(self, request, view):
        """Check permissions for article access."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        if not hasattr(request.user, 'profile'):
            return False
        
        # Admins have full access
        if request.user.profile.role == UserRole.ADMIN:
            return True
        
        # Technicians have read-only access
        if request.user.profile.role == UserRole.TECH:
            return request.method in permissions.SAFE_METHODS
        
        return False


class DemandPermissions(permissions.BasePermission):
    """
    Custom permissions for Demand management.
    - Technicians: can view and create their own demands
    - Admins: full access to all demands
    """
    
    def has_permission(self, request, view):
        """Check permissions for demand access."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        if not hasattr(request.user, 'profile'):
            return False
        
        return request.user.profile.role in [UserRole.TECH, UserRole.ADMIN]
    
    def has_object_permission(self, request, view, obj):
        """Check object-level permissions for demands."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        if not hasattr(request.user, 'profile'):
            return False
        
        # Admins can access all demands
        if request.user.profile.role == UserRole.ADMIN:
            return True
        
        # Technicians can only access their own demands
        if request.user.profile.role == UserRole.TECH:
            return obj.technician == request.user.profile
        
        return False
