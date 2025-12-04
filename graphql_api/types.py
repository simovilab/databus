import strawberry
from typing import Optional, TYPE_CHECKING
import datetime
from decimal import Decimal

if TYPE_CHECKING:
    from gtfs.models import Feed, Agency, Route, Stop, Trip, StopTime


@strawberry.type
class FeedType:
    """GraphQL type for Feed model"""

    id: int
    name: str
    url: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime


@strawberry.type
class AgencyType:
    """GraphQL type for Agency model"""

    id: int
    agency_id: str
    agency_name: str
    agency_url: str
    agency_timezone: str
    agency_lang: Optional[str]
    agency_phone: Optional[str]
    agency_fare_url: Optional[str]
    agency_email: Optional[str]
    feed_id: int


@strawberry.type
class StopType:
    """GraphQL type for Stop model"""

    id: int
    stop_id: str
    stop_code: Optional[str]
    stop_name: str
    stop_desc: Optional[str]
    stop_lat: float
    stop_lon: float
    zone_id: Optional[str]
    stop_url: Optional[str]
    location_type: int
    parent_station: Optional[str]
    stop_timezone: Optional[str]
    wheelchair_boarding: Optional[int]
    feed_id: int


@strawberry.type
class RouteType:
    """GraphQL type for Route model"""

    id: int
    route_id: str
    route_short_name: str
    route_long_name: str
    route_desc: Optional[str]
    route_type: int
    route_url: Optional[str]
    route_color: Optional[str]
    route_text_color: Optional[str]
    route_sort_order: Optional[int]
    feed_id: int
    agency_id: Optional[int]


@strawberry.type
class CalendarType:
    """GraphQL type for Calendar model"""

    id: int
    service_id: str
    monday: bool
    tuesday: bool
    wednesday: bool
    thursday: bool
    friday: bool
    saturday: bool
    sunday: bool
    start_date: datetime.date
    end_date: datetime.date
    feed_id: int


@strawberry.type
class TripType:
    """GraphQL type for Trip model"""

    id: int
    trip_id: str
    trip_headsign: Optional[str]
    trip_short_name: Optional[str]
    direction_id: Optional[int]
    block_id: Optional[str]
    shape_id: Optional[str]
    wheelchair_accessible: int
    bikes_allowed: int
    service_id: str
    feed_id: int
    route_id: int


@strawberry.type
class StopTimeType:
    """GraphQL type for StopTime model"""

    id: int
    stop_sequence: int
    stop_headsign: Optional[str]
    pickup_type: int
    drop_off_type: int
    shape_dist_traveled: Optional[float]
    timepoint: int
    feed_id: int
    trip_id: int
    stop_id: int
    arrival_time_str: Optional[str]
    departure_time_str: Optional[str]


@strawberry.type
class FareAttributeType:
    """GraphQL type for FareAttribute model"""

    id: int
    fare_id: str
    price: str
    currency_type: str
    payment_method: int
    transfers: Optional[int]
    transfer_duration: Optional[int]
    feed_id: int


@strawberry.type
class ShapeType:
    """GraphQL type for Shape model"""

    id: int
    shape_id: str
    shape_pt_lat: float
    shape_pt_lon: float
    shape_pt_sequence: int
    shape_dist_traveled: Optional[float]
    feed_id: int


@strawberry.type
class PageInfo:
    """Information about pagination"""

    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str]
    end_cursor: Optional[str]
    total_count: int


@strawberry.type
class AgencyConnection:
    """Paginated list of agencies"""

    edges: list[AgencyType]
    page_info: PageInfo


@strawberry.type
class RouteConnection:
    """Paginated list of routes"""

    edges: list[RouteType]
    page_info: PageInfo


@strawberry.type
class StopConnection:
    """Paginated list of stops"""

    edges: list[StopType]
    page_info: PageInfo


@strawberry.type
class TripConnection:
    """Paginated list of trips"""

    edges: list[TripType]
    page_info: PageInfo


@strawberry.type
class StopTimeConnection:
    """Paginated list of stop times"""

    edges: list[StopTimeType]
    page_info: PageInfo


@strawberry.input
class CreateAgencyInput:
    """Input for creating an agency"""

    feed_id: int
    agency_id: str
    agency_name: str
    agency_url: str
    agency_timezone: str
    agency_lang: Optional[str] = None
    agency_phone: Optional[str] = None
    agency_fare_url: Optional[str] = None
    agency_email: Optional[str] = None


@strawberry.type
class CreateAgencyPayload:
    """Result of creating an agency"""

    agency: Optional[AgencyType]
    errors: list[str]
    success: bool


def agency_to_type(agency) -> AgencyType:
    """Convert Agency model to AgencyType"""
    return AgencyType(
        id=agency.id,
        agency_id=agency.agency_id,
        agency_name=agency.agency_name,
        agency_url=agency.agency_url,
        agency_timezone=agency.agency_timezone,
        agency_lang=agency.agency_lang or None,
        agency_phone=agency.agency_phone or None,
        agency_fare_url=agency.agency_fare_url or None,
        agency_email=agency.agency_email or None,
        feed_id=agency.feed_id,
    )


def feed_to_type(feed) -> FeedType:
    """Convert Feed model to FeedType"""
    return FeedType(
        id=feed.id,
        name=feed.name,
        url=feed.url,
        created_at=feed.created_at,
        updated_at=feed.updated_at,
    )


def route_to_type(route) -> RouteType:
    """Convert Route model to RouteType"""
    return RouteType(
        id=route.id,
        route_id=route.route_id,
        route_short_name=route.route_short_name,
        route_long_name=route.route_long_name,
        route_desc=route.route_desc or None,
        route_type=route.route_type,
        route_url=route.route_url or None,
        route_color=route.route_color or None,
        route_text_color=route.route_text_color or None,
        route_sort_order=route.route_sort_order,
        feed_id=route.feed_id,
        agency_id=route.agency_id,
    )


def stop_to_type(stop) -> StopType:
    """Convert Stop model to StopType"""
    return StopType(
        id=stop.id,
        stop_id=stop.stop_id,
        stop_code=stop.stop_code or None,
        stop_name=stop.stop_name,
        stop_desc=stop.stop_desc or None,
        stop_lat=stop.stop_lat,
        stop_lon=stop.stop_lon,
        zone_id=stop.zone_id or None,
        stop_url=stop.stop_url or None,
        location_type=stop.location_type,
        parent_station=stop.parent_station or None,
        stop_timezone=stop.stop_timezone or None,
        wheelchair_boarding=stop.wheelchair_boarding,
        feed_id=stop.feed_id,
    )


def trip_to_type(trip) -> TripType:
    """Convert Trip model to TripType"""
    return TripType(
        id=trip.id,
        trip_id=trip.trip_id,
        trip_headsign=trip.trip_headsign or None,
        trip_short_name=trip.trip_short_name or None,
        direction_id=trip.direction_id,
        block_id=trip.block_id or None,
        shape_id=trip.shape_id or None,
        wheelchair_accessible=trip.wheelchair_accessible,
        bikes_allowed=trip.bikes_allowed,
        service_id=trip.service_id,
        feed_id=trip.feed_id,
        route_id=trip.route_id,
    )


def stop_time_to_type(stop_time) -> StopTimeType:
    """Convert StopTime model to StopTimeType"""
    arrival_time_str = None
    if stop_time.arrival_time:
        total_seconds = int(stop_time.arrival_time.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        arrival_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    departure_time_str = None
    if stop_time.departure_time:
        total_seconds = int(stop_time.departure_time.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        departure_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return StopTimeType(
        id=stop_time.id,
        stop_sequence=stop_time.stop_sequence,
        stop_headsign=stop_time.stop_headsign or None,
        pickup_type=stop_time.pickup_type,
        drop_off_type=stop_time.drop_off_type,
        shape_dist_traveled=stop_time.shape_dist_traveled,
        timepoint=stop_time.timepoint,
        feed_id=stop_time.feed_id,
        trip_id=stop_time.trip_id,
        stop_id=stop_time.stop_id,
        arrival_time_str=arrival_time_str,
        departure_time_str=departure_time_str,
    )
