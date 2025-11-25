# Simulador de Telemetría - Databus

El simulador de telemetría proporciona una plataforma de prueba para el sistema Databus antes de instalar equipos reales en los buses.

## Instalación y Configuración

### 1. Agregar a settings.py

La app `simulator` ya está incluida en `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "simulator.apps.SimulatorConfig",
    # ...
]
```

### 2. Crear migraciones y migrar

```bash
# Dentro del contenedor
docker-compose exec web python manage.py makemigrations simulator
docker-compose exec web python manage.py migrate simulator

# O usando el script
./scripts/migrate.sh
```

### 3. Verificar Celery Beat

Asegúrate de que Celery Beat esté ejecutándose para las actualizaciones periódicas:

```bash
docker-compose ps
```

Deberías ver el servicio `beat` corriendo.

## Uso Rápido

### Iniciar simulación de todos los vehículos

```bash
docker-compose exec web python manage.py start_simulation --all
```

### Iniciar simulación de un vehículo específico

```bash
docker-compose exec web python manage.py start_simulation --vehicle SJB9876
```

### Con velocidad personalizada

```bash
docker-compose exec web python manage.py start_simulation --vehicle SJB9876 --speed 15.0
```

### Detener simulaciones

```bash
# Detener todas
docker-compose exec web python manage.py stop_simulation --all

# Detener una específica
docker-compose exec web python manage.py stop_simulation --vehicle SJB9876
```

## Monitoreo

### Panel de administración

1. Accede a `/admin/simulator/`
2. **Simulated Vehicles**: Ver y configurar vehículos simulados
3. **Simulation Logs**: Ver registro de eventos de simulación

### Verificar datos generados

```bash
# Ver posiciones recientes
docker-compose exec web python manage.py shell
>>> from feed.models import Position
>>> Position.objects.order_by('-timestamp')[:10]

# Ver viajes activos
>>> from feed.models import Journey
>>> Journey.objects.filter(journey_status='IN_PROGRESS')
```

## Funcionamiento

### Flujo de datos

1. **Inicio de viaje**: El simulador selecciona un trip GTFS y crea un Journey
2. **Actualizaciones de posición**: Cada 10 segundos se actualiza la posición del vehículo siguiendo los shape points
3. **Llegada a paradas**: Cuando el vehículo se acerca a una parada (< 50m), se actualiza:
   - Progression (estado en parada)
   - Occupancy (ocupación del vehículo)
4. **Fin de viaje**: Cuando completa todos los shape points, el viaje se marca como completado

### Tareas periódicas de Celery

Configuradas en `realtime/celery.py`:

- **update_simulated_positions**: Cada 10 segundos
- **cleanup_simulation_logs**: Diariamente a las 2:00 AM (limpia logs > 7 días)

### Datos generados

El simulador crea registros en estos modelos:

- `Journey`: Viajes simulados
- `Position`: Posiciones GPS cada 10 segundos
- `Progression`: Estado en paradas
- `Occupancy`: Ocupación del vehículo en paradas

## Parámetros de simulación

Configurable en el admin o programáticamente:

- **speed**: Velocidad de simulación en m/s (default: 10.0)
- **update_interval**: Intervalo de actualización de posición en segundos (default: 10)
- **is_active**: Habilitar/deshabilitar simulación

## Prerrequisitos

Para que el simulador funcione correctamente, necesitas:

1. **Datos GTFS cargados**:
   - Routes
   - Trips
   - Stops
   - StopTimes
   - Shapes

2. **Vehículos configurados**:
   - Vehicles en la base de datos
   - Equipment con `provides_position=True` (opcional)

3. **Operadores**:
   - Al menos un Operator en la base de datos

## Ejemplos de comandos útiles

### Verificar estado de simulación

```bash
docker-compose exec web python manage.py shell
>>> from simulator.models import SimulatedVehicle
>>> sims = SimulatedVehicle.objects.filter(is_active=True)
>>> for sim in sims:
...     print(f"{sim.vehicle.license_plate}: Journey {sim.current_journey_id}, Stop {sim.current_stop_index}")
```

### Verificar logs recientes

```bash
docker-compose exec web python manage.py shell
>>> from simulator.models import SimulationLog
>>> logs = SimulationLog.objects.order_by('-timestamp')[:20]
>>> for log in logs:
...     print(f"{log.timestamp}: {log.event_type} - {log.message}")
```

### Limpiar logs manualmente

```bash
docker-compose exec web python manage.py shell
>>> from simulator.simulator import SimulationManager
>>> deleted = SimulationManager.cleanup_old_logs(days=7)
>>> print(f"Deleted {deleted} logs")
```

## API y GTFS Realtime

Los datos generados por el simulador están disponibles a través de:

- **API REST**: `/api/position/`, `/api/journey/`, `/api/occupancy/`, etc.
- **GTFS Realtime**: Feed generado automáticamente con los datos simulados

## Troubleshooting

### No se crean posiciones

**Problema**: El simulador está activo pero no genera posiciones.

**Solución**:
1. Verifica que Celery Beat esté corriendo: `docker-compose ps`
2. Revisa los logs de Celery: `docker-compose logs beat`
3. Verifica que haya shape points: `Shape.objects.filter(shape_id='shape_123').count()`
4. Revisa SimulationLog para errores: `/admin/simulator/simulationlog/`

### Vehículos no tienen viajes

**Problema**: Los vehículos simulados no inician viajes.

**Solución**:
1. Verifica que existan trips: `Trip.objects.count()`
2. Verifica que exista al menos un operador: `Operator.objects.count()`
3. Revisa los logs de simulación para ver mensajes de error

### Occupancy no se actualiza

**Problema**: Las posiciones se actualizan pero no la ocupación.

**Solución**:
1. Verifica que haya StopTimes configurados para el trip
2. Verifica que los stops tengan coordenadas válidas
3. La ocupación solo se actualiza cuando el vehículo está cerca (<50m) de una parada

### Celery Beat no ejecuta tareas

**Problema**: Las tareas periódicas no se ejecutan.

**Solución**:
1. Reinicia Celery Beat: `docker-compose restart beat`
2. Verifica la configuración en `realtime/celery.py`
3. Revisa logs: `docker-compose logs beat`

## Limpieza

### Detener todas las simulaciones

```bash
docker-compose exec web python manage.py stop_simulation --all
```

### Eliminar datos de simulación

```bash
docker-compose exec web python manage.py shell
>>> from simulator.models import SimulatedVehicle, SimulationLog
>>> SimulatedVehicle.objects.all().delete()
>>> SimulationLog.objects.all().delete()
>>>
>>> # También puedes eliminar los datos generados
>>> from feed.models import Journey, Position, Occupancy
>>> Journey.objects.filter(journey_status='IN_PROGRESS').delete()
>>> # Cuidado: esto elimina TODOS los datos, incluso reales
>>> Position.objects.all().delete()
>>> Occupancy.objects.all().delete()
```

## Próximos pasos

1. **Configurar datos GTFS**: Importa routes, trips, stops, shapes
2. **Crear vehículos**: Agrega vehículos en el admin
3. **Crear operador**: Agrega al menos un operador
4. **Iniciar simulación**: Usa los comandos de management
5. **Monitorear**: Revisa el admin y los logs

## Integración con "Proyecto Células TP"

El simulador está diseñado para ser compatible con el concepto de "buses como sensores rodantes":

- Simula datos de telemetría realistas
- Permite probar la infraestructura antes del despliegue
- Genera datos compatibles con GTFS Realtime
- Preparado para integración con NGSI-LD (ver `docs/ngsi-ld-compatibility.md`)

## Referencias

- [README del Simulador](simulator/README.md) - Documentación técnica detallada
- [Documentación del API](docs/api.md) - Endpoints disponibles
- [Celery Configuration](realtime/celery.py) - Configuración de tareas periódicas
- [GTFS Models](gtfs/models.py) - Modelos GTFS utilizados
- [Feed Models](feed/models.py) - Modelos de telemetría
