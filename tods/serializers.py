"""
DRF serializers for TODS models.
"""
from rest_framework import serializers
from .models import (
    Operator,
    Run,
    RunPiece,
    RunEvent,
    Deadhead,
    DeadheadStopTime,
    RosterAssignment,
)


class OperatorSerializer(serializers.ModelSerializer):
    """Serializer for transit operators."""
    
    operator_type_display = serializers.CharField(source='get_operator_type_display', read_only=True)
    
    class Meta:
        model = Operator
        fields = [
            'id',
            'feed',
            'operator_id',
            'operator_name',
            'operator_type',
            'operator_type_display',
            'operator_license',
            'operator_phone',
            'operator_email',
        ]


class RunPieceSerializer(serializers.ModelSerializer):
    """Serializer for run pieces."""
    
    piece_type_display = serializers.CharField(source='get_piece_type_display', read_only=True)
    
    class Meta:
        model = RunPiece
        fields = [
            'id',
            'feed',
            'run_piece_id',
            'run',
            'piece_type',
            'piece_type_display',
            'start_time',
            'end_time',
            'piece_sequence',
        ]


class RunEventSerializer(serializers.ModelSerializer):
    """Serializer for run events."""
    
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    
    class Meta:
        model = RunEvent
        fields = [
            'id',
            'feed',
            'run_event_id',
            'run_piece',
            'event_type',
            'event_type_display',
            'event_time',
            'stop',
            'event_duration',
        ]


class RunSerializer(serializers.ModelSerializer):
    """Serializer for runs with nested pieces."""
    
    pieces = RunPieceSerializer(many=True, read_only=True)
    operator_name = serializers.CharField(source='operator.operator_name', read_only=True)
    
    class Meta:
        model = Run
        fields = [
            'id',
            'feed',
            'run_id',
            'run_name',
            'operator',
            'operator_name',
            'pieces',
        ]


class DeadheadStopTimeSerializer(serializers.ModelSerializer):
    """Serializer for deadhead stop times."""
    
    stop_name = serializers.CharField(source='stop.stop_name', read_only=True)
    
    class Meta:
        model = DeadheadStopTime
        fields = [
            'id',
            'stop',
            'stop_name',
            'arrival_time',
            'departure_time',
            'stop_sequence',
        ]


class DeadheadSerializer(serializers.ModelSerializer):
    """Serializer for deadheads with nested stop times."""
    
    deadhead_type_display = serializers.CharField(source='get_deadhead_type_display', read_only=True)
    stop_times = DeadheadStopTimeSerializer(many=True, read_only=True)
    from_stop_name = serializers.CharField(source='from_stop.stop_name', read_only=True)
    to_stop_name = serializers.CharField(source='to_stop.stop_name', read_only=True)
    
    class Meta:
        model = Deadhead
        fields = [
            'id',
            'feed',
            'deadhead_id',
            'deadhead_name',
            'deadhead_type',
            'deadhead_type_display',
            'from_trip',
            'to_trip',
            'from_stop',
            'from_stop_name',
            'to_stop',
            'to_stop_name',
            'start_time',
            'end_time',
            'run_piece',
            'stop_times',
        ]


class RosterAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for roster assignments."""
    
    operator_name = serializers.CharField(source='operator.operator_name', read_only=True)
    run_name = serializers.CharField(source='run.run_name', read_only=True)
    
    class Meta:
        model = RosterAssignment
        fields = [
            'id',
            'feed',
            'roster_id',
            'operator',
            'operator_name',
            'run',
            'run_name',
            'assignment_date',
        ]
