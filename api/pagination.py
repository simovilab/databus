"""
Custom pagination classes for Databús API.

Implements sensible defaults and maximum caps for API pagination.
"""

from rest_framework.pagination import (
    PageNumberPagination,
    LimitOffsetPagination,
    CursorPagination,
)
from rest_framework.response import Response
from collections import OrderedDict


class StandardPageNumberPagination(PageNumberPagination):
    """
    Standard pagination for most API endpoints.
    
    Default: 50 items per page
    Max: 100 items per page
    Query param: page, page_size
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        """Return paginated response with metadata."""
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('page_size', self.page.paginator.per_page),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('results', data)
        ]))


class SmallResultSetPagination(PageNumberPagination):
    """
    Pagination for small result sets (e.g., agencies, operators).
    
    Default: 25 items per page
    Max: 50 items per page
    """
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 50


class LargeResultSetPagination(PageNumberPagination):
    """
    Pagination for large result sets (e.g., stop times, shapes).
    
    Default: 100 items per page
    Max: 500 items per page
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500


class RealtimeFeedPagination(PageNumberPagination):
    """
    Pagination for realtime feeds (vehicles, alerts, trip updates).
    
    Default: 50 items per page
    Max: 200 items per page
    
    Realtime data changes frequently, so we allow larger page sizes
    for efficiency but cap it to prevent abuse.
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class StandardLimitOffsetPagination(LimitOffsetPagination):
    """
    Limit/Offset pagination for flexible access patterns.
    
    Default limit: 50
    Max limit: 100
    Query params: limit, offset
    """
    default_limit = 50
    max_limit = 100
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    
    def get_paginated_response(self, data):
        """Return paginated response with metadata."""
        return Response(OrderedDict([
            ('count', self.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('limit', self.limit),
            ('offset', self.offset),
            ('results', data)
        ]))


class VehiclePositionCursorPagination(CursorPagination):
    """
    Cursor-based pagination for vehicle positions.
    
    Cursor pagination is more efficient for large datasets and
    prevents issues with data changing between page requests.
    
    Ordered by: timestamp (descending)
    Page size: 50
    Max page size: 200
    """
    page_size = 50
    max_page_size = 200
    ordering = '-timestamp'
    cursor_query_param = 'cursor'
    page_size_query_param = 'page_size'


class TripUpdateCursorPagination(CursorPagination):
    """
    Cursor-based pagination for trip updates.
    
    Ordered by: timestamp (descending)
    Page size: 50
    Max page size: 200
    """
    page_size = 50
    max_page_size = 200
    ordering = '-timestamp'
    cursor_query_param = 'cursor'
    page_size_query_param = 'page_size'


class AuditLogCursorPagination(CursorPagination):
    """
    Cursor-based pagination for audit logs.
    
    Audit logs are append-only and can be very large,
    making cursor pagination ideal.
    
    Ordered by: timestamp (descending)
    Page size: 100
    Max page size: 500
    """
    page_size = 100
    max_page_size = 500
    ordering = '-timestamp'
    cursor_query_param = 'cursor'
    page_size_query_param = 'page_size'


class NoPagination(PageNumberPagination):
    """
    Special pagination class for endpoints that should return all results.
    
    Use with caution and only for small, bounded datasets.
    Max: 1000 items
    """
    page_size = None
    max_page_size = 1000
    
    def paginate_queryset(self, queryset, request, view=None):
        """Return queryset without pagination if count is under limit."""
        count = queryset.count()
        if count > self.max_page_size:
            # Force pagination if too large
            self.page_size = 100
            return super().paginate_queryset(queryset, request, view)
        return None  # No pagination needed


# Pagination class mapping for easy configuration
PAGINATION_CLASSES = {
    'standard': StandardPageNumberPagination,
    'small': SmallResultSetPagination,
    'large': LargeResultSetPagination,
    'realtime': RealtimeFeedPagination,
    'limit_offset': StandardLimitOffsetPagination,
    'cursor': VehiclePositionCursorPagination,
    'trip_updates': TripUpdateCursorPagination,
    'audit_log': AuditLogCursorPagination,
    'none': NoPagination,
}


def get_pagination_class(name='standard'):
    """
    Get pagination class by name.
    
    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            pagination_class = get_pagination_class('large')
    """
    return PAGINATION_CLASSES.get(name, StandardPageNumberPagination)
