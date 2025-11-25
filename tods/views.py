"""
DRF views for TODS endpoints.
"""
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import (
    Operator,
    Run,
    RunPiece,
    RunEvent,
    Deadhead,
    DeadheadStopTime,
    RosterAssignment,
)
from .serializers import (
    OperatorSerializer,
    RunSerializer,
    RunPieceSerializer,
    RunEventSerializer,
    DeadheadSerializer,
    DeadheadStopTimeSerializer,
    RosterAssignmentSerializer,
)


class OperatorViewSet(viewsets.ModelViewSet):
    """
    API endpoint for transit operators.
    
    list: Get all operators
    retrieve: Get a specific operator by ID
    create: Create a new operator
    update: Update an existing operator
    destroy: Delete an operator
    
    Filters:
    - operator_type: Filter by operator type (0=Bus, 1=Rail, etc.)
    - feed: Filter by feed ID
    """
    
    queryset = Operator.objects.all()
    serializer_class = OperatorSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['operator_type', 'feed']
    search_fields = ['operator_id', 'operator_name', 'operator_license']
    ordering_fields = ['operator_name', 'operator_id']
    ordering = ['operator_name']


class RunViewSet(viewsets.ModelViewSet):
    """
    API endpoint for runs (work sequences).
    
    list: Get all runs
    retrieve: Get a specific run with nested pieces
    create: Create a new run
    update: Update an existing run
    destroy: Delete a run
    
    Filters:
    - operator: Filter by operator ID
    - feed: Filter by feed ID
    """
    
    queryset = Run.objects.select_related('operator').prefetch_related('pieces')
    serializer_class = RunSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['operator', 'feed']
    search_fields = ['run_id', 'run_name']
    ordering_fields = ['run_id']
    ordering = ['run_id']


class RunPieceViewSet(viewsets.ModelViewSet):
    """
    API endpoint for run pieces (work segments).
    
    list: Get all run pieces
    retrieve: Get a specific run piece
    create: Create a new run piece
    update: Update an existing run piece
    destroy: Delete a run piece
    
    Filters:
    - run: Filter by run ID
    - piece_type: Filter by piece type (0=Revenue, 1=Deadhead, etc.)
    - feed: Filter by feed ID
    """
    
    queryset = RunPiece.objects.select_related('run')
    serializer_class = RunPieceSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['run', 'piece_type', 'feed']
    ordering_fields = ['run', 'piece_sequence']
    ordering = ['run', 'piece_sequence']


class RunEventViewSet(viewsets.ModelViewSet):
    """
    API endpoint for run events (breaks, sign-on/off, etc.).
    
    list: Get all run events
    retrieve: Get a specific run event
    create: Create a new run event
    update: Update an existing run event
    destroy: Delete a run event
    
    Filters:
    - run_piece: Filter by run piece ID
    - event_type: Filter by event type
    - feed: Filter by feed ID
    """
    
    queryset = RunEvent.objects.select_related('run_piece', 'stop')
    serializer_class = RunEventSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['run_piece', 'event_type', 'feed']
    ordering_fields = ['run_piece', 'event_time']
    ordering = ['run_piece', 'event_time']


class DeadheadViewSet(viewsets.ModelViewSet):
    """
    API endpoint for deadheads (non-revenue movements).
    
    list: Get all deadheads
    retrieve: Get a specific deadhead with stop times
    create: Create a new deadhead
    update: Update an existing deadhead
    destroy: Delete a deadhead
    
    Filters:
    - deadhead_type: Filter by type (0=Pullout, 1=Pullin, etc.)
    - from_trip: Filter by origin trip
    - to_trip: Filter by destination trip
    - run_piece: Filter by run piece
    - feed: Filter by feed ID
    """
    
    queryset = Deadhead.objects.select_related(
        'from_trip', 'to_trip', 'from_stop', 'to_stop', 'run_piece'
    ).prefetch_related('stop_times')
    serializer_class = DeadheadSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['deadhead_type', 'from_trip', 'to_trip', 'run_piece', 'feed']
    search_fields = ['deadhead_id', 'deadhead_name']
    ordering_fields = ['deadhead_id', 'start_time']
    ordering = ['start_time']


class DeadheadStopTimeViewSet(viewsets.ModelViewSet):
    """
    API endpoint for deadhead stop times.
    
    list: Get all deadhead stop times
    retrieve: Get a specific deadhead stop time
    create: Create a new deadhead stop time
    update: Update an existing deadhead stop time
    destroy: Delete a deadhead stop time
    
    Filters:
    - deadhead: Filter by deadhead ID
    """
    
    queryset = DeadheadStopTime.objects.select_related('deadhead', 'stop')
    serializer_class = DeadheadStopTimeSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['deadhead']
    ordering_fields = ['deadhead', 'stop_sequence']
    ordering = ['deadhead', 'stop_sequence']


class RosterAssignmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for roster assignments.
    
    list: Get all roster assignments
    retrieve: Get a specific roster assignment
    create: Create a new roster assignment
    update: Update an existing roster assignment
    destroy: Delete a roster assignment
    
    Filters:
    - operator: Filter by operator ID
    - run: Filter by run ID
    - assignment_date: Filter by date (exact match)
    - feed: Filter by feed ID
    """
    
    queryset = RosterAssignment.objects.select_related('operator', 'run')
    serializer_class = RosterAssignmentSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['operator', 'run', 'assignment_date', 'feed']
    ordering_fields = ['assignment_date', 'operator']
    ordering = ['-assignment_date']
