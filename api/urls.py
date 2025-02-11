from django.urls import include, path
from rest_framework import routers
from rest_framework.authtoken.views import obtain_auth_token
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

from . import views

router = routers.DefaultRouter()
router.register(r"company", views.CompanyViewSet)
router.register(r"operator", views.OperatorViewSet)
router.register(r"data-provider", views.DataProviderViewSet)
router.register(r"vehicle", views.VehicleViewSet)
router.register(r"equipment", views.EquipmentViewSet)
router.register(r"journey", views.JourneyViewSet)
router.register(r"position", views.PositionViewSet)
router.register(r"progression", views.ProgressionViewSet)
router.register(r"occupancy", views.OccupancyViewSet)
# GTFS Schedule
router.register(r"agency", views.AgencyViewSet)
router.register(r"stops", views.StopViewSet)
router.register(r"geo-stops", views.GeoStopViewSet, basename='geo-stop')
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
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("docs/schema/", views.get_schema, name="schema"),
    path("docs/", SpectacularRedocView.as_view(url_name="schema"), name="api_docs"),
]
