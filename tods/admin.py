"""
Django admin configuration for TODS models.
"""
from django.contrib import admin
from .models import (
    Operator,
    Run,
    RunPiece,
    RunEvent,
    Deadhead,
    DeadheadStopTime,
    RosterAssignment,
)


@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ('operator_id', 'operator_name', 'operator_type', 'operator_phone', 'feed')
    list_filter = ('operator_type', 'feed')
    search_fields = ('operator_id', 'operator_name', 'operator_license', 'operator_email')
    ordering = ('operator_name',)


class RunPieceInline(admin.TabularInline):
    model = RunPiece
    extra = 1
    fields = ('run_piece_id', 'piece_type', 'start_time', 'end_time', 'piece_sequence')
    ordering = ('piece_sequence',)


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ('run_id', 'run_name', 'operator', 'feed')
    list_filter = ('feed', 'operator')
    search_fields = ('run_id', 'run_name')
    inlines = [RunPieceInline]


class RunEventInline(admin.TabularInline):
    model = RunEvent
    extra = 1
    fields = ('run_event_id', 'event_type', 'event_time', 'stop', 'event_duration')


@admin.register(RunPiece)
class RunPieceAdmin(admin.ModelAdmin):
    list_display = ('run_piece_id', 'run', 'piece_type', 'start_time', 'end_time', 'piece_sequence')
    list_filter = ('piece_type', 'run__feed')
    search_fields = ('run_piece_id', 'run__run_id')
    ordering = ('run', 'piece_sequence')
    inlines = [RunEventInline]


@admin.register(RunEvent)
class RunEventAdmin(admin.ModelAdmin):
    list_display = ('run_event_id', 'run_piece', 'event_type', 'event_time', 'stop', 'event_duration')
    list_filter = ('event_type', 'run_piece__feed')
    search_fields = ('run_event_id',)
    ordering = ('run_piece', 'event_time')


class DeadheadStopTimeInline(admin.TabularInline):
    model = DeadheadStopTime
    extra = 1
    fields = ('stop', 'arrival_time', 'departure_time', 'stop_sequence')
    ordering = ('stop_sequence',)


@admin.register(Deadhead)
class DeadheadAdmin(admin.ModelAdmin):
    list_display = ('deadhead_id', 'deadhead_type', 'from_stop', 'to_stop', 'start_time', 'end_time', 'run_piece')
    list_filter = ('deadhead_type', 'feed')
    search_fields = ('deadhead_id', 'deadhead_name')
    inlines = [DeadheadStopTimeInline]


@admin.register(DeadheadStopTime)
class DeadheadStopTimeAdmin(admin.ModelAdmin):
    list_display = ('deadhead', 'stop', 'arrival_time', 'departure_time', 'stop_sequence')
    list_filter = ('deadhead__feed',)
    ordering = ('deadhead', 'stop_sequence')


@admin.register(RosterAssignment)
class RosterAssignmentAdmin(admin.ModelAdmin):
    list_display = ('roster_id', 'operator', 'run', 'assignment_date', 'feed')
    list_filter = ('assignment_date', 'feed')
    search_fields = ('roster_id', 'operator__operator_name', 'run__run_id')
    ordering = ('-assignment_date', 'operator')
    date_hierarchy = 'assignment_date'
