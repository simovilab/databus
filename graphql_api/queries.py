import strawberry
from strawberry.types import Info
from typing import Optional, List
from django.core.paginator import Paginator
from gtfs.models import Agency, Route, Stop, Trip, StopTime, Feed
from .types import (
    AgencyType,
    RouteType,
    StopType,
    TripType,
    StopTimeType,
    FeedType,
    AgencyConnection,
    RouteConnection,
    StopConnection,
    TripConnection,
    StopTimeConnection,
    PageInfo,
    agency_to_type,
    feed_to_type,
    route_to_type,
    stop_to_type,
    trip_to_type,
    stop_time_to_type,
)
from .permissions import IsAuthenticated
import base64


def create_page_info(paginator, page_obj, offset: int, limit: int) -> PageInfo:
    """Helper function to create PageInfo object"""
    total_count = paginator.count
    has_next = page_obj.has_next()
    has_previous = page_obj.has_previous()

    start_cursor = (
        base64.b64encode(f"{offset}".encode()).decode() if offset >= 0 else None
    )
    end_cursor = (
        base64.b64encode(f"{offset + limit}".encode()).decode()
        if offset + limit < total_count
        else None
    )

    return PageInfo(
        has_next_page=has_next,
        has_previous_page=has_previous,
        start_cursor=start_cursor,
        end_cursor=end_cursor,
        total_count=total_count,
    )


@strawberry.type
class Query:
    """Root Query type for GraphQL API"""

    @strawberry.field(permission_classes=[IsAuthenticated])
    def all_feeds(self, info: Info) -> List[FeedType]:
        """Get all feeds"""
        return [feed_to_type(f) for f in Feed.objects.all()]

    @strawberry.field(permission_classes=[IsAuthenticated])
    def feed(self, info: Info, id: int) -> Optional[FeedType]:
        """Get a single feed by ID"""
        try:
            return feed_to_type(Feed.objects.get(id=id))
        except Feed.DoesNotExist:
            return None

    @strawberry.field(permission_classes=[IsAuthenticated])
    def all_agencies(
        self,
        info: Info,
        offset: int = 0,
        limit: int = 20,
        feed_id: Optional[int] = None,
        name_contains: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> AgencyConnection:
        """Get all agencies with pagination and filtering"""
        limit = min(limit, 100)
        queryset = Agency.objects.select_related("feed").all()

        if feed_id is not None:
            queryset = queryset.filter(feed_id=feed_id)
        if name_contains:
            queryset = queryset.filter(agency_name__icontains=name_contains)
        if timezone:
            queryset = queryset.filter(agency_timezone=timezone)

        queryset = queryset.order_by("agency_name")
        paginator = Paginator(queryset, limit)
        page_number = (offset // limit) + 1
        page_obj = paginator.get_page(page_number)
        page_info = create_page_info(paginator, page_obj, offset, limit)

        return AgencyConnection(
            edges=[agency_to_type(a) for a in page_obj],
            page_info=page_info
        )

    @strawberry.field(permission_classes=[IsAuthenticated])
    def agency(self, info: Info, id: int) -> Optional[AgencyType]:
        """Get a single agency by ID"""
        try:
            return agency_to_type(Agency.objects.select_related("feed").get(id=id))
        except Agency.DoesNotExist:
            return None

    @strawberry.field(permission_classes=[IsAuthenticated])
    def all_routes(
        self,
        info: Info,
        offset: int = 0,
        limit: int = 20,
        feed_id: Optional[int] = None,
        agency_id: Optional[int] = None,
        route_type: Optional[int] = None,
        short_name_contains: Optional[str] = None,
    ) -> RouteConnection:
        """Get all routes with pagination and filtering"""
        limit = min(limit, 100)
        queryset = Route.objects.select_related("feed", "agency").all()

        if feed_id is not None:
            queryset = queryset.filter(feed_id=feed_id)
        if agency_id is not None:
            queryset = queryset.filter(agency_id=agency_id)
        if route_type is not None:
            queryset = queryset.filter(route_type=route_type)
        if short_name_contains:
            queryset = queryset.filter(route_short_name__icontains=short_name_contains)

        queryset = queryset.order_by("route_short_name")
        paginator = Paginator(queryset, limit)
        page_number = (offset // limit) + 1
        page_obj = paginator.get_page(page_number)
        page_info = create_page_info(paginator, page_obj, offset, limit)

        return RouteConnection(
            edges=[route_to_type(r) for r in page_obj],
            page_info=page_info
        )

    @strawberry.field(permission_classes=[IsAuthenticated])
    def route(self, info: Info, id: int) -> Optional[RouteType]:
        """Get a single route by ID"""
        try:
            return route_to_type(Route.objects.select_related("feed", "agency").get(id=id))
        except Route.DoesNotExist:
            return None

    @strawberry.field(permission_classes=[IsAuthenticated])
    def all_stops(
        self,
        info: Info,
        offset: int = 0,
        limit: int = 20,
        feed_id: Optional[int] = None,
        name_contains: Optional[str] = None,
        location_type: Optional[int] = None,
    ) -> StopConnection:
        """Get all stops with pagination and filtering"""
        limit = min(limit, 100)
        queryset = Stop.objects.select_related("feed").all()

        if feed_id is not None:
            queryset = queryset.filter(feed_id=feed_id)
        if name_contains:
            queryset = queryset.filter(stop_name__icontains=name_contains)
        if location_type is not None:
            queryset = queryset.filter(location_type=location_type)

        queryset = queryset.order_by("stop_name")
        paginator = Paginator(queryset, limit)
        page_number = (offset // limit) + 1
        page_obj = paginator.get_page(page_number)
        page_info = create_page_info(paginator, page_obj, offset, limit)

        return StopConnection(
            edges=[stop_to_type(s) for s in page_obj],
            page_info=page_info
        )

    @strawberry.field(permission_classes=[IsAuthenticated])
    def stop(self, info: Info, id: int) -> Optional[StopType]:
        """Get a single stop by ID"""
        try:
            return stop_to_type(Stop.objects.select_related("feed").get(id=id))
        except Stop.DoesNotExist:
            return None

    @strawberry.field(permission_classes=[IsAuthenticated])
    def trips_by_route(
        self,
        info: Info,
        route_id: int,
        offset: int = 0,
        limit: int = 20,
        direction_id: Optional[int] = None,
        service_id: Optional[str] = None,
    ) -> TripConnection:
        """Get trips for a specific route with pagination and filtering"""
        limit = min(limit, 100)
        queryset = Trip.objects.select_related("feed", "route").filter(route_id=route_id)

        if direction_id is not None:
            queryset = queryset.filter(direction_id=direction_id)
        if service_id:
            queryset = queryset.filter(service_id=service_id)

        queryset = queryset.order_by("trip_id")
        paginator = Paginator(queryset, limit)
        page_number = (offset // limit) + 1
        page_obj = paginator.get_page(page_number)
        page_info = create_page_info(paginator, page_obj, offset, limit)

        return TripConnection(
            edges=[trip_to_type(t) for t in page_obj],
            page_info=page_info
        )

    @strawberry.field(permission_classes=[IsAuthenticated])
    def trip(self, info: Info, id: int) -> Optional[TripType]:
        """Get a single trip by ID"""
        try:
            return trip_to_type(Trip.objects.select_related("feed", "route").get(id=id))
        except Trip.DoesNotExist:
            return None

    @strawberry.field(permission_classes=[IsAuthenticated])
    def stop_times_by_trip(
        self,
        info: Info,
        trip_id: int,
        offset: int = 0,
        limit: int = 100,
    ) -> StopTimeConnection:
        """Get stop times for a specific trip, ordered by stop sequence"""
        limit = min(limit, 200)
        queryset = (
            StopTime.objects.select_related("feed", "trip", "stop")
            .filter(trip_id=trip_id)
            .order_by("stop_sequence")
        )

        paginator = Paginator(queryset, limit)
        page_number = (offset // limit) + 1
        page_obj = paginator.get_page(page_number)
        page_info = create_page_info(paginator, page_obj, offset, limit)

        return StopTimeConnection(
            edges=[stop_time_to_type(st) for st in page_obj],
            page_info=page_info
        )

    @strawberry.field(permission_classes=[IsAuthenticated])
    def stop_time(self, info: Info, id: int) -> Optional[StopTimeType]:
        """Get a single stop time by ID"""
        try:
            return stop_time_to_type(StopTime.objects.select_related("feed", "trip", "stop").get(id=id))
        except StopTime.DoesNotExist:
            return None
