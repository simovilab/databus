from django.urls import include, path
from rest_framework import routers
from rest_framework.authtoken.views import obtain_auth_token
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

from . import views

router = routers.DefaultRouter()
router.register(r"vehicle", views.VehicleViewSet)
router.register(r"operator", views.OperatorViewSet)
router.register(r"provider", views.DataProviderViewSet)
router.register(r"equipment", views.EquipmentViewSet)
router.register(r"journey", views.JourneyViewSet)
router.register(r"position", views.PositionViewSet)
router.register(r"progression", views.ProgressionViewSet)
router.register(r"occupancy", views.OccupancyViewSet)

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
