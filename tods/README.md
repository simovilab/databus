# TODS (Transit Operational Data Standard) API

## Descripción

El módulo TODS extiende Databús con datos operativos de tránsito siguiendo el estándar **Transit Operational Data Standard (TODS)**, que es una extensión de GTFS.

Mientras que GTFS se enfoca en información útil para pasajeros (horarios, rutas, paradas), TODS añade información operativa interna necesaria para operar el servicio:

- **Personal**: Operadores, supervisores, despachadores
- **Runs**: Secuencias de trabajo para operadores
- **Deadheads**: Movimientos sin pasajeros (pullouts, pullins, reposicionamiento)
- **Asignaciones**: Roster de turnos para personal
- **Eventos operativos**: Sign-on, sign-off, breaks, fueling, etc.

## Especificación

TODS sigue la especificación oficial: https://github.com/TODS-Spec/TODS

## Arquitectura

### Modelos Django

| Modelo | Descripción | Archivo TODS |
|--------|-------------|--------------|
| `Operator` | Operadores/conductores de vehículos | `operators.txt` |
| `Run` | Secuencia de trabajo para un operador | `runs.txt` |
| `RunPiece` | Pieza de trabajo dentro de un run | `run_pieces.txt` |
| `RunEvent` | Eventos dentro de un run (breaks, sign-on, etc.) | `run_events.txt` |
| `Deadhead` | Movimientos sin pasajeros | `deadheads.txt` |
| `DeadheadStopTime` | Tiempos de paradas en deadheads | `deadhead_stop_times.txt` |
| `RosterAssignment` | Asignación de operadores a runs | `roster_assignments.txt` |

### Relaciones

```
Feed (GTFS)
  ├── Operator (múltiples operadores)
  │     └── RosterAssignment (asignaciones diarias)
  │           └── Run (turnos de trabajo)
  │                 └── RunPiece (segmentos de trabajo)
  │                       ├── RunEvent (eventos operativos)
  │                       └── Deadhead (movimientos sin pasajeros)
  │                             └── DeadheadStopTime (paradas del deadhead)
  └── Trip (GTFS)
        └── Deadhead (puede estar vinculado a trips)
```

## API Endpoints

Todos los endpoints están bajo `/api/tods/` y siguen los estándares REST de DRF.

### Operators

**GET** `/api/tods/operators/`
- Lista todos los operadores
- **Filtros**: `operator_type`, `feed`
- **Búsqueda**: `operator_id`, `operator_name`, `operator_license`

**Ejemplo de respuesta:**
```json
{
  "count": 10,
  "results": [
    {
      "id": 1,
      "feed": "cr_mopt",
      "operator_id": "OP001",
      "operator_name": "Juan Pérez Rodríguez",
      "operator_type": 0,
      "operator_type_display": "Bus operator",
      "operator_license": "LIC123456",
      "operator_phone": "+50688888888",
      "operator_email": "juan.perez@example.com"
    }
  ]
}
```

**Tipos de operador:**
- `0`: Bus operator
- `1`: Rail operator
- `2`: Ferry operator
- `3`: Supervisor
- `4`: Dispatcher
- `5`: Maintenance
- `99`: Other

### Runs

**GET** `/api/tods/runs/`
- Lista todos los runs (turnos de trabajo)
- **Filtros**: `operator`, `feed`
- **Búsqueda**: `run_id`, `run_name`

**GET** `/api/tods/runs/{id}/`
- Detalle de un run con todas sus piezas de trabajo

**Ejemplo de respuesta:**
```json
{
  "id": 1,
  "feed": "cr_mopt",
  "run_id": "RUN_101",
  "run_name": "Morning Route 1 - Full Shift",
  "operator": 1,
  "operator_name": "Juan Pérez Rodríguez",
  "pieces": [
    {
      "id": 1,
      "run_piece_id": "PIECE_101_1",
      "piece_type": 3,
      "piece_type_display": "Sign on",
      "start_time": "06:00:00",
      "end_time": "06:15:00",
      "piece_sequence": 1
    },
    {
      "id": 2,
      "run_piece_id": "PIECE_101_2",
      "piece_type": 0,
      "piece_type_display": "Revenue service",
      "start_time": "06:15:00",
      "end_time": "14:00:00",
      "piece_sequence": 2
    }
  ]
}
```

### Run Pieces

**GET** `/api/tods/run-pieces/`
- Lista todas las piezas de trabajo
- **Filtros**: `run`, `piece_type`, `feed`

**Tipos de pieza:**
- `0`: Revenue service (servicio con pasajeros)
- `1`: Deadhead (sin pasajeros)
- `2`: Break (descanso)
- `3`: Sign on (inicio de turno)
- `4`: Sign off (fin de turno)
- `5`: Fueling (combustible)
- `6`: Maintenance (mantenimiento)
- `99`: Other

### Run Events

**GET** `/api/tods/run-events/`
- Lista todos los eventos operativos
- **Filtros**: `run_piece`, `event_type`, `feed`

**Tipos de evento:**
- `0`: Sign on
- `1`: Sign off
- `2`: Break start
- `3`: Break end
- `4`: Meal break start
- `5`: Meal break end
- `6`: Fuel
- `7`: Maintenance
- `8`: Pullout (salida de cochera)
- `9`: Pullin (entrada a cochera)
- `99`: Other

### Deadheads

**GET** `/api/tods/deadheads/`
- Lista todos los movimientos sin pasajeros
- **Filtros**: `deadhead_type`, `from_trip`, `to_trip`, `run_piece`, `feed`

**GET** `/api/tods/deadheads/{id}/`
- Detalle de un deadhead con todos sus stop times

**Ejemplo de respuesta:**
```json
{
  "id": 1,
  "feed": "cr_mopt",
  "deadhead_id": "DH_001",
  "deadhead_name": "Pullout to Terminal Central",
  "deadhead_type": 0,
  "deadhead_type_display": "Pullout",
  "from_stop": 500,
  "from_stop_name": "Garage Principal",
  "to_stop": 100,
  "to_stop_name": "Terminal Central",
  "start_time": "05:30:00",
  "end_time": "05:50:00",
  "run_piece": 1,
  "stop_times": [
    {
      "id": 1,
      "stop": 500,
      "stop_name": "Garage Principal",
      "departure_time": "05:30:00",
      "stop_sequence": 1
    },
    {
      "id": 2,
      "stop": 100,
      "stop_name": "Terminal Central",
      "arrival_time": "05:50:00",
      "stop_sequence": 2
    }
  ]
}
```

**Tipos de deadhead:**
- `0`: Pullout (desde cochera al primer viaje con pasajeros)
- `1`: Pullin (desde último viaje con pasajeros a cochera)
- `2`: Between trips (entre viajes con pasajeros)
- `3`: Repositioning (reposicionamiento)
- `4`: Fueling
- `5`: Maintenance
- `99`: Other

### Roster Assignments

**GET** `/api/tods/roster-assignments/`
- Lista todas las asignaciones de roster
- **Filtros**: `operator`, `run`, `assignment_date`, `feed`

**Ejemplo de respuesta:**
```json
{
  "count": 50,
  "results": [
    {
      "id": 1,
      "feed": "cr_mopt",
      "roster_id": "ROSTER_2025_11_25_001",
      "operator": 1,
      "operator_name": "Juan Pérez Rodríguez",
      "run": 1,
      "run_name": "Morning Route 1 - Full Shift",
      "assignment_date": "2025-11-25"
    }
  ]
}
```

## Casos de Uso

### 1. Consultar el turno de un operador específico

```bash
# Obtener runs del operador con ID=1
curl http://localhost:8000/api/tods/runs/?operator=1
```

### 2. Ver todas las asignaciones de hoy

```bash
curl http://localhost:8000/api/tods/roster-assignments/?assignment_date=2025-11-25
```

### 3. Listar todos los pullouts del día

```bash
# deadhead_type=0 es Pullout
curl http://localhost:8000/api/tods/deadheads/?deadhead_type=0
```

### 4. Ver el horario completo de un run con todas sus piezas

```bash
curl http://localhost:8000/api/tods/runs/1/
```

### 5. Encontrar todos los breaks de un operador

```bash
# Primero obtener los runs del operador
# Luego filtrar run-pieces por piece_type=2 (Break)
curl http://localhost:8000/api/tods/run-pieces/?run=1&piece_type=2
```

## Integración con GTFS

TODS está diseñado para complementar GTFS, no reemplazarlo:

- **GTFS** → Información para pasajeros (horarios, rutas, paradas)
- **TODS** → Información operativa interna (personal, deadheads, turnos)

### Extensiones a modelos GTFS

TODS añade campos opcionales a modelos GTFS existentes:

- `Trip.block_id`: Bloque al que pertenece el trip
- `Trip.run_id`: Run que ejecuta el trip
- `StopTime.timepoint`: Si la parada es un punto de control horario

Estos campos se añadirán mediante migrations en futuras versiones.

## Ejemplo de Flujo Operativo Completo

Un día típico de operación:

1. **05:30** - **Sign on**: Operador llega a cochera
2. **05:30-05:50** - **Pullout (Deadhead)**: Viaje sin pasajeros desde cochera a terminal
3. **06:00-14:00** - **Revenue service**: Múltiples trips con pasajeros
4. **10:00-10:30** - **Break**: Descanso del operador
5. **14:00-14:20** - **Pullin (Deadhead)**: Viaje sin pasajeros de regreso a cochera
6. **14:20** - **Sign off**: Fin de turno

Este flujo se representa en TODS como:
- 1 `Run` (turno completo)
- 5 `RunPiece` (Sign on, Pullout, Revenue service, Pullin, Sign off)
- 2 `Deadhead` (Pullout y Pullin con sus stop times)
- Múltiples `RunEvent` (breaks, fueling si aplica)
- 1 `RosterAssignment` (asignación del día)

## Administración Django

Todos los modelos TODS están disponibles en el Django Admin:

- `/admin/tods/operator/`
- `/admin/tods/run/`
- `/admin/tods/runpiece/`
- `/admin/tods/runevent/`
- `/admin/tods/deadhead/`
- `/admin/tods/deadheadstoptime/`
- `/admin/tods/rosterassignment/`

Incluyen:
- Filtros por tipo, fecha, operador
- Búsqueda por IDs y nombres
- Inlines para editar relaciones anidadas (e.g., run pieces dentro de runs)

## Testing

Ejecutar tests de TODS:

```bash
python manage.py test tods
```

Tests incluyen:
- Creación de modelos
- Relaciones entre entidades
- Endpoints API
- Filtros y búsquedas

## Migración de Datos

Para importar datos TODS desde archivos `.txt`:

```python
# TODO: Crear management commands para importar TODS
python manage.py import_tods_operators <operators.txt>
python manage.py import_tods_runs <runs.txt>
python manage.py import_tods_deadheads <deadheads.txt>
```

## Referencias

- **TODS Specification**: https://github.com/TODS-Spec/TODS
- **GTFS Schedule**: https://gtfs.org/schedule/reference/
- **ARC-IT**: https://www.arc-it.net/ (para contexto de arquitectura ITS)

## Próximos Pasos

1. ✅ Modelos Django implementados
2. ✅ Serializadores DRF implementados
3. ✅ Endpoints API funcionando
4. ✅ Tests unitarios
5. ⏳ Management commands para importar datos TODS
6. ⏳ Integración con simulador (simular deadheads)
7. ⏳ Añadir campos TODS a modelos GTFS (block_id, run_id, timepoint)
8. ⏳ Dashboard operativo para supervisores
