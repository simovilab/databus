"""
URL routing for TODS API endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OperatorViewSet,
    RunViewSet,
    RunPieceViewSet,
    RunEventViewSet,
    DeadheadViewSet,
    DeadheadStopTimeViewSet,
    RosterAssignmentViewSet,
)

router = DefaultRouter()
router.register(r'operators', OperatorViewSet, basename='operator')
router.register(r'runs', RunViewSet, basename='run')
router.register(r'run-pieces', RunPieceViewSet, basename='runpiece')
router.register(r'run-events', RunEventViewSet, basename='runevent')
router.register(r'deadheads', DeadheadViewSet, basename='deadhead')
router.register(r'deadhead-stop-times', DeadheadStopTimeViewSet, basename='deadheadstoptime')
router.register(r'roster-assignments', RosterAssignmentViewSet, basename='rosterassignment')

urlpatterns = [
    path('', include(router.urls)),
]
