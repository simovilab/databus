from django.contrib import admin
from .models import SimulatedVehicle, SimulationLog


@admin.register(SimulatedVehicle)
class SimulatedVehicleAdmin(admin.ModelAdmin):
    list_display = [
        'vehicle',
        'equipment',
        'is_active',
        'current_journey',
        'current_stop_index',
        'speed',
        'updated_at'
    ]
    list_filter = ['is_active', 'updated_at']
    search_fields = ['vehicle__license_plate', 'vehicle__label']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Vehicle Information', {
            'fields': ('vehicle', 'equipment', 'is_active')
        }),
        ('Journey State', {
            'fields': ('current_journey', 'current_stop_index', 'current_shape_index')
        }),
        ('Simulation Parameters', {
            'fields': ('speed', 'update_interval')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SimulationLog)
class SimulationLogAdmin(admin.ModelAdmin):
    list_display = [
        'simulated_vehicle',
        'event_type',
        'timestamp',
        'message'
    ]
    list_filter = ['event_type', 'timestamp']
    search_fields = [
        'simulated_vehicle__vehicle__license_plate',
        'message'
    ]
    readonly_fields = ['timestamp', 'data']
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Event Information', {
            'fields': ('simulated_vehicle', 'event_type', 'timestamp')
        }),
        ('Details', {
            'fields': ('message', 'data')
        }),
    )
    
    def has_add_permission(self, request):
        # Logs should only be created by the system
        return False
