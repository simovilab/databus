from django.urls import include, path
from rest_framework import routers
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

from . import views

router = routers.DefaultRouter()
router.register(r"vehicle", views.VehicleViewSet)
router.register(r"equipment", views.EquipmentViewSet)
router.register(r"trip", views.TripViewSet)
router.register(r"position", views.PositionViewSet)
router.register(r"path", views.PathViewSet)
router.register(r"occupancy", views.OccupancyViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path("", include(router.urls)),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("docs/schema/", views.get_schema, name="schema"),
    path("docs/", SpectacularRedocView.as_view(url_name="schema"), name="api_docs"),
]
