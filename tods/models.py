"""
TODS models following the Transit Operational Data Standard specification.
https://github.com/TODS-Spec/TODS
"""
from django.contrib.gis.db import models
from django.core.validators import MinValueValidator
from gtfs.models import Feed, Trip, Stop


class Operator(models.Model):
    """
    Transit operator/driver information.
    Maps to operators.txt in TODS.
    """
    
    OPERATOR_TYPE_CHOICES = [
        (0, 'Bus operator'),
        (1, 'Rail operator'),
        (2, 'Ferry operator'),
        (3, 'Supervisor'),
        (4, 'Dispatcher'),
        (5, 'Maintenance'),
        (99, 'Other'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    feed = models.ForeignKey(Feed, to_field='feed_id', on_delete=models.CASCADE)
    operator_id = models.CharField(
        max_length=255,
        help_text="Identificador único del operador."
    )
    operator_name = models.CharField(
        max_length=255,
        help_text="Nombre completo del operador."
    )
    operator_type = models.IntegerField(
        choices=OPERATOR_TYPE_CHOICES,
        default=0,
        help_text="Tipo de operador."
    )
    operator_license = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Número de licencia del operador."
    )
    operator_phone = models.CharField(
        max_length=63,
        blank=True,
        null=True,
        help_text="Teléfono de contacto del operador."
    )
    operator_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email del operador."
    )
    
    class Meta:
        db_table = 'tods_operators'
        unique_together = ('feed', 'operator_id')
    
    def __str__(self):
        return f"{self.operator_name} ({self.operator_id})"


class Run(models.Model):
    """
    A run is a sequence of work performed by one operator.
    Maps to runs.txt in TODS.
    """
    
    id = models.BigAutoField(primary_key=True)
    feed = models.ForeignKey(Feed, to_field='feed_id', on_delete=models.CASCADE)
    run_id = models.CharField(
        max_length=255,
        help_text="Identificador único del run."
    )
    run_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Nombre descriptivo del run."
    )
    operator = models.ForeignKey(
        Operator,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="Operador asignado al run."
    )
    
    class Meta:
        db_table = 'tods_runs'
        unique_together = ('feed', 'run_id')
    
    def __str__(self):
        return f"Run {self.run_id}"


class RunPiece(models.Model):
    """
    A piece of work within a run.
    Maps to run_pieces.txt in TODS.
    """
    
    PIECE_TYPE_CHOICES = [
        (0, 'Revenue service'),
        (1, 'Deadhead'),
        (2, 'Break'),
        (3, 'Sign on'),
        (4, 'Sign off'),
        (5, 'Fueling'),
        (6, 'Maintenance'),
        (99, 'Other'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    feed = models.ForeignKey(Feed, to_field='feed_id', on_delete=models.CASCADE)
    run_piece_id = models.CharField(
        max_length=255,
        help_text="Identificador único de la pieza de trabajo."
    )
    run = models.ForeignKey(
        Run,
        on_delete=models.CASCADE,
        related_name='pieces',
        help_text="Run al que pertenece esta pieza."
    )
    piece_type = models.IntegerField(
        choices=PIECE_TYPE_CHOICES,
        default=0,
        help_text="Tipo de pieza de trabajo."
    )
    start_time = models.TimeField(
        help_text="Hora de inicio de la pieza (HH:MM:SS)."
    )
    end_time = models.TimeField(
        help_text="Hora de fin de la pieza (HH:MM:SS)."
    )
    piece_sequence = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Secuencia de la pieza dentro del run."
    )
    
    class Meta:
        db_table = 'tods_run_pieces'
        unique_together = ('feed', 'run_piece_id')
        ordering = ['run', 'piece_sequence']
    
    def __str__(self):
        return f"Piece {self.run_piece_id} - {self.get_piece_type_display()}"


class RunEvent(models.Model):
    """
    Events within a run piece (breaks, sign-on/off, etc.).
    Maps to run_events.txt in TODS.
    """
    
    EVENT_TYPE_CHOICES = [
        (0, 'Sign on'),
        (1, 'Sign off'),
        (2, 'Break start'),
        (3, 'Break end'),
        (4, 'Meal break start'),
        (5, 'Meal break end'),
        (6, 'Fuel'),
        (7, 'Maintenance'),
        (8, 'Pullout'),
        (9, 'Pullin'),
        (99, 'Other'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    feed = models.ForeignKey(Feed, to_field='feed_id', on_delete=models.CASCADE)
    run_event_id = models.CharField(
        max_length=255,
        help_text="Identificador único del evento."
    )
    run_piece = models.ForeignKey(
        RunPiece,
        on_delete=models.CASCADE,
        related_name='events',
        help_text="Pieza de trabajo en la que ocurre el evento."
    )
    event_type = models.IntegerField(
        choices=EVENT_TYPE_CHOICES,
        help_text="Tipo de evento."
    )
    event_time = models.TimeField(
        help_text="Hora del evento (HH:MM:SS)."
    )
    stop = models.ForeignKey(
        Stop,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="Parada donde ocurre el evento (opcional)."
    )
    event_duration = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        help_text="Duración del evento en minutos (para breaks)."
    )
    
    class Meta:
        db_table = 'tods_run_events'
        unique_together = ('feed', 'run_event_id')
        ordering = ['run_piece', 'event_time']
    
    def __str__(self):
        return f"Event {self.run_event_id} - {self.get_event_type_display()}"


class Deadhead(models.Model):
    """
    Non-revenue vehicle movements (deadheads).
    Maps to deadheads.txt in TODS.
    """
    
    DEADHEAD_TYPE_CHOICES = [
        (0, 'Pullout'),  # From garage to first revenue trip
        (1, 'Pullin'),   # From last revenue trip to garage
        (2, 'Between trips'),  # Between two revenue trips
        (3, 'Repositioning'),  # Vehicle repositioning
        (4, 'Fueling'),
        (5, 'Maintenance'),
        (99, 'Other'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    feed = models.ForeignKey(Feed, to_field='feed_id', on_delete=models.CASCADE)
    deadhead_id = models.CharField(
        max_length=255,
        help_text="Identificador único del deadhead."
    )
    deadhead_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Nombre descriptivo del deadhead."
    )
    deadhead_type = models.IntegerField(
        choices=DEADHEAD_TYPE_CHOICES,
        default=2,
        help_text="Tipo de movimiento sin pasajeros."
    )
    from_trip = models.ForeignKey(
        Trip,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='deadheads_from',
        help_text="Trip de origen (si aplica)."
    )
    to_trip = models.ForeignKey(
        Trip,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='deadheads_to',
        help_text="Trip de destino (si aplica)."
    )
    from_stop = models.ForeignKey(
        Stop,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='deadheads_from_stop',
        help_text="Parada de origen del deadhead."
    )
    to_stop = models.ForeignKey(
        Stop,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='deadheads_to_stop',
        help_text="Parada de destino del deadhead."
    )
    start_time = models.TimeField(
        help_text="Hora de inicio del deadhead (HH:MM:SS)."
    )
    end_time = models.TimeField(
        help_text="Hora de fin del deadhead (HH:MM:SS)."
    )
    run_piece = models.ForeignKey(
        RunPiece,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='deadheads',
        help_text="Pieza de trabajo asociada."
    )
    
    class Meta:
        db_table = 'tods_deadheads'
        unique_together = ('feed', 'deadhead_id')
    
    def __str__(self):
        return f"Deadhead {self.deadhead_id} - {self.get_deadhead_type_display()}"


class DeadheadStopTime(models.Model):
    """
    Stop times for deadhead movements.
    Maps to deadhead_stop_times.txt in TODS.
    """
    
    id = models.BigAutoField(primary_key=True)
    deadhead = models.ForeignKey(
        Deadhead,
        on_delete=models.CASCADE,
        related_name='stop_times',
        help_text="Deadhead al que pertenece este tiempo."
    )
    stop = models.ForeignKey(
        Stop,
        on_delete=models.CASCADE,
        help_text="Parada en la ruta del deadhead."
    )
    arrival_time = models.TimeField(
        blank=True,
        null=True,
        help_text="Hora de llegada a la parada (HH:MM:SS)."
    )
    departure_time = models.TimeField(
        blank=True,
        null=True,
        help_text="Hora de salida de la parada (HH:MM:SS)."
    )
    stop_sequence = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Secuencia de la parada en el deadhead."
    )
    
    class Meta:
        db_table = 'tods_deadhead_stop_times'
        unique_together = ('deadhead', 'stop_sequence')
        ordering = ['deadhead', 'stop_sequence']
    
    def __str__(self):
        return f"Deadhead {self.deadhead.deadhead_id} - Stop {self.stop_sequence}"


class RosterAssignment(models.Model):
    """
    Assignment of operators to runs (roster).
    Maps to roster_assignments.txt in TODS.
    """
    
    id = models.BigAutoField(primary_key=True)
    feed = models.ForeignKey(Feed, to_field='feed_id', on_delete=models.CASCADE)
    roster_id = models.CharField(
        max_length=255,
        help_text="Identificador único de la asignación."
    )
    operator = models.ForeignKey(
        Operator,
        on_delete=models.CASCADE,
        related_name='assignments',
        help_text="Operador asignado."
    )
    run = models.ForeignKey(
        Run,
        on_delete=models.CASCADE,
        related_name='assignments',
        help_text="Run asignado."
    )
    assignment_date = models.DateField(
        help_text="Fecha de la asignación."
    )
    
    class Meta:
        db_table = 'tods_roster_assignments'
        unique_together = ('feed', 'roster_id')
        ordering = ['assignment_date', 'operator']
    
    def __str__(self):
        return f"{self.operator.operator_name} -> Run {self.run.run_id} ({self.assignment_date})"


# Extensiones a modelos GTFS existentes (se añadirán campos via migrations)
# Para añadir block_id y run_id a Trip, y timepoint a StopTime
