from django.db import models
from feed.models import Vehicle, Equipment, Journey


class SimulatedVehicle(models.Model):
    """
    Configuration for a simulated vehicle.
    """
    vehicle = models.OneToOneField(
        Vehicle, 
        on_delete=models.CASCADE,
        related_name='simulation'
    )
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this vehicle is currently being simulated"
    )
    current_journey = models.ForeignKey(
        Journey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Current simulated journey"
    )
    current_stop_index = models.IntegerField(
        default=0,
        help_text="Index of current stop in the journey"
    )
    current_shape_index = models.IntegerField(
        default=0,
        help_text="Index of current shape point"
    )
    speed = models.FloatField(
        default=10.0,
        help_text="Simulated speed in m/s"
    )
    update_interval = models.IntegerField(
        default=10,
        help_text="Position update interval in seconds"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Simulated Vehicle"
        verbose_name_plural = "Simulated Vehicles"

    def __str__(self):
        return f"Simulation: {self.vehicle.license_plate}"


class SimulationLog(models.Model):
    """
    Log of simulation events for debugging and monitoring.
    """
    simulated_vehicle = models.ForeignKey(
        SimulatedVehicle,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(
        max_length=50,
        choices=[
            ('JOURNEY_START', 'Journey Started'),
            ('JOURNEY_END', 'Journey Ended'),
            ('POSITION_UPDATE', 'Position Updated'),
            ('STOP_ARRIVAL', 'Arrived at Stop'),
            ('STOP_DEPARTURE', 'Departed from Stop'),
            ('OCCUPANCY_UPDATE', 'Occupancy Updated'),
            ('ERROR', 'Error Occurred'),
        ]
    )
    message = models.TextField(blank=True)
    data = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = "Simulation Log"
        verbose_name_plural = "Simulation Logs"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.simulated_vehicle} - {self.event_type} at {self.timestamp}"
