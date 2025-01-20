from django.urls import include, path
from rest_framework import routers
from rest_framework.authtoken.views import obtain_auth_token
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

from . import views

router = routers.DefaultRouter()
router.register(r"data-provider", views.DataProviderViewSet)
router.register(r"vehicle", views.VehicleViewSet)
router.register(r"equipment", views.EquipmentViewSet)
router.register(r"operator", views.OperatorViewSet)
router.register(r"journey", views.JourneyViewSet)
router.register(r"position", views.PositionViewSet)
router.register(r"progression", views.ProgressionViewSet)
router.register(r"occupancy", views.OccupancyViewSet)
# GTFS Schedule
router.register(r"gtfs/schedule/agencies", views.AgencyViewSet)
router.register(r"gtfs/schedule/stops", views.StopViewSet)
router.register(r"gtfs/schedule/geo-stops", views.GeoStopViewSet, basename='geo-stop')
router.register(r"gtfs/schedule/shapes", views.ShapeViewSet)
router.register(r"gtfs/schedule/geo-shapes", views.GeoShapeViewSet)
router.register(r"gtfs/schedule/routes", views.RouteViewSet)
router.register(r"gtfs/schedule/calendars", views.CalendarViewSet)
router.register(r"gtfs/schedule/calendar-dates", views.CalendarDateViewSet)
router.register(r"gtfs/schedule/trips", views.TripViewSet)
router.register(r"gtfs/schedule/stop-times", views.StopTimeViewSet)
router.register(r"gtfs/schedule/fare-attributes", views.FareAttributeViewSet)
router.register(r"gtfs/schedule/fare-rules", views.FareRuleViewSet)
router.register(r"gtfs/schedule/feed-info", views.FeedInfoViewSet)


# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path("", include(router.urls)),
    path("login/", obtain_auth_token, name="login"),
    path("find-trips/", views.FindTripsView.as_view(), name="find_trips"),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("docs/schema/", views.get_schema, name="schema"),
    path("docs/", SpectacularRedocView.as_view(url_name="schema"), name="api_docs"),
]
