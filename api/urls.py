from django.urls import include, path
from rest_framework import routers
from rest_framework.authtoken.views import obtain_auth_token
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

from . import views
from . import category_views
from . import jwt_views
from . import client_views

router = routers.DefaultRouter()
router.register(r"company", views.CompanyViewSet)
router.register(r"operator", views.OperatorViewSet)
router.register(r"data-provider", views.DataProviderViewSet)
router.register(r"vehicle", views.VehicleViewSet)
router.register(r"equipment", views.EquipmentViewSet)
router.register(r"equipment-log", views.EquipmentLogViewSet)
router.register(r"journey", views.JourneyViewSet)
router.register(r"position", views.PositionViewSet)
router.register(r"progression", views.ProgressionViewSet)
router.register(r"occupancy", views.OccupancyViewSet)
# API Client Registry
router.register(r"clients", client_views.APIClientViewSet, basename="client")
router.register(r"client-metrics", client_views.ClientUsageMetricsViewSet, basename="client-metrics")
router.register(r"client-audit", client_views.ClientAuditLogViewSet, basename="client-audit")
# GTFS Schedule
router.register(r"agency", views.AgencyViewSet)
router.register(r"stops", views.StopViewSet)
router.register(r"geo-stops", views.GeoStopViewSet, basename="geo-stop")
router.register(r"shapes", views.ShapeViewSet)
router.register(r"geo-shapes", views.GeoShapeViewSet)
router.register(r"routes", views.RouteViewSet)
router.register(r"calendars", views.CalendarViewSet)
router.register(r"calendar-dates", views.CalendarDateViewSet)
router.register(r"trips", views.TripViewSet)
router.register(r"stop-times", views.StopTimeViewSet)
router.register(r"fare-attributes", views.FareAttributeViewSet)
router.register(r"fare-rules", views.FareRuleViewSet)
router.register(r"feed-info", views.FeedInfoViewSet)


# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path("", include(router.urls)),
    path("login/", views.LoginView.as_view(), name="login"),
    # path("route-stops/", views.RouteStopView.as_view(), name="route_stops"),
    path("service-today/", views.ServiceTodayView.as_view(), name="service_today"),
    path("which-shapes/", views.WhichShapesView.as_view(), name="which_shapes"),
    path("find-trips/", views.FindTripsView.as_view(), name="find_trips"),
    # GTFS Categories
    path("route-types/", category_views.RouteTypeListView.as_view(), name="route_types"),
    path("location-types/", category_views.LocationTypeListView.as_view(), name="location_types"),
    path("wheelchair-accessibility/", category_views.WheelchairAccessibilityListView.as_view(), name="wheelchair_accessibility"),
    path("pickup-dropoff-types/", category_views.PickupDropoffTypeListView.as_view(), name="pickup_dropoff_types"),
    path("payment-methods/", category_views.PaymentMethodListView.as_view(), name="payment_methods"),
    path("transfer-types/", category_views.TransferTypeListView.as_view(), name="transfer_types"),
    # JWT Authentication
    path("auth/token/", jwt_views.CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", jwt_views.CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/verify/", jwt_views.TokenVerifyView.as_view(), name="token_verify"),
    path("auth/logout/", jwt_views.LogoutView.as_view(), name="logout"),
    # DRF Auth & Docs
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("docs/schema/", views.get_schema, name="schema"),
    path("docs/", views.RedocView.as_view(url_name="schema"), name="api_docs"),
]
