# Issue #16: Incorporar TODS al API - Implementation Summary

## Overview
Integration of Transit Operational Data Standard (TODS) into Databus API for operational transit data management.

## Implementation Status
✅ **COMPLETE** - TODS models, API endpoints, and tests fully implemented

## Implementation Date
November 2025

## What is TODS?

**TODS (Transit Operational Data Standard)** extends GTFS to include operational data:
- Personnel/operator assignments
- Run and duty management
- Deadhead trips (non-revenue service)
- Roster assignments
- Operational events

Specification: https://github.com/TODS-Spec/TODS

## Files Implemented

### Models (`tods/models.py`)

#### 1. **Operators** (maps to `operators.txt`)
```python
class Operators(models.Model):
    operator_id: CharField(primary key)
    operator_type: IntegerField (0=operator, 1=vehicle, 2=service)
    operator_name: CharField
    operator_phone: CharField (nullable)
    operator_license_no: CharField (nullable)
```

**Purpose**: Represents transit operators (drivers, vehicles, services)

#### 2. **Runs** (maps to `runs.txt`)
```python
class Runs(models.Model):
    run_id: CharField(primary key)
    route: ForeignKey(Route)
    service: ForeignKey(Calendar)
    start_type, end_type: IntegerField (0=start of day, 1=terminal, etc.)
```

**Purpose**: Defines operator runs/duties

#### 3. **RunPieces** (maps to `run_pieces.txt`)
```python
class RunPieces(models.Model):
    run: ForeignKey(Runs)
    piece_type: IntegerField (0=trip, 1=deadhead, 2=break, etc.)
    trip: ForeignKey(Trip, nullable)
    deadhead: ForeignKey(Deadheads, nullable)
    start_time, end_time: TimeField
    piece_sequence: IntegerField
```

**Purpose**: Components of a run (trips, deadheads, breaks)

#### 4. **RunEvents** (maps to `run_events.txt`)
```python
class RunEvents(models.Model):
    run: ForeignKey(Runs)
    event_type: IntegerField (0=sign-in, 1=pull-out, 2=pull-in, etc.)
    event_time: TimeField
    event_duration: DurationField
    event_from_stop, event_to_stop: ForeignKey(Stop, nullable)
    sequence: IntegerField
```

**Purpose**: Operational events within a run

#### 5. **Deadheads** (maps to `deadheads.txt`)
```python
class Deadheads(models.Model):
    deadhead_id: CharField(primary key)
    service: ForeignKey(Calendar)
    deadhead_name: CharField (nullable)
    block_id: CharField (nullable)
```

**Purpose**: Non-revenue service movements

#### 6. **DeadheadStopTimes** (maps to `deadhead_stop_times.txt`)
```python
class DeadheadStopTimes(models.Model):
    deadhead: ForeignKey(Deadheads)
    arrival_time, departure_time: TimeField
    stop: ForeignKey(Stop)
    stop_sequence: IntegerField
```

**Purpose**: Stop times for deadhead trips

#### 7. **RosterAssignments** (maps to `roster_assignments.txt`)
```python
class RosterAssignments(models.Model):
    operator: ForeignKey(Operators)
    run: ForeignKey(Runs)
    assignment_date: DateField
```

**Purpose**: Assigns operators to runs

### API Endpoints (`tods/views.py`, `tods/urls.py`)

#### Operators
- `GET /api/tods/operators/` - List all operators
- `GET /api/tods/operators/{id}/` - Get operator details
- **Filters**: operator_type

#### Runs
- `GET /api/tods/runs/` - List all runs
- `GET /api/tods/runs/{id}/` - Get run details
- **Filters**: route, service

#### Run Pieces
- `GET /api/tods/run-pieces/` - List run pieces
- `GET /api/tods/run-pieces/{id}/` - Get piece details
- **Filters**: run, piece_type

#### Run Events
- `GET /api/tods/run-events/` - List run events
- `GET /api/tods/run-events/{id}/` - Get event details
- **Filters**: run, event_type

#### Deadheads
- `GET /api/tods/deadheads/` - List deadheads
- `GET /api/tods/deadheads/{id}/` - Get deadhead details
- **Filters**: service

#### Deadhead Stop Times
- `GET /api/tods/deadhead-stop-times/` - List stop times
- **Filters**: deadhead

#### Roster Assignments
- `GET /api/tods/roster-assignments/` - List assignments
- **Filters**: operator, run, assignment_date

### Serializers (`tods/serializers.py`)

All models have corresponding serializers for API responses:
- `OperatorSerializer`
- `RunSerializer`
- `RunPieceSerializer`
- `RunEventSerializer`
- `DeadheadSerializer`
- `DeadheadStopTimeSerializer`
- `RosterAssignmentSerializer`

### Admin Interface (`tods/admin.py`)

Django admin registered for all TODS models:
- List display, filters, search
- Inline editing for related models
- Custom actions

### Tests (`tods/tests.py`)

**Test Classes**:
1. `TODSModelsTestCase`: Model creation and relationships (8 tests)
2. `TODSAPITestCase`: API endpoint tests (6 tests)

**Total**: 14 TODS-specific tests

### Configuration

#### `realtime/settings.py`
```python
INSTALLED_APPS = [
    ...
    "tods.apps.TodsConfig",
]
```

#### `realtime/urls.py`
```python
urlpatterns = [
    ...
    path("api/tods/", include("tods.urls")),
]
```

## Data Model Relationships

```
Operators ←──→ RosterAssignments ←──→ Runs
                                        ├──→ Route (GTFS)
                                        ├──→ Service (GTFS Calendar)
                                        └──→ RunPieces
                                             ├──→ Trip (GTFS)
                                             ├──→ Deadheads
                                             │    └──→ DeadheadStopTimes
                                             │         └──→ Stop (GTFS)
                                             └──→ RunEvents
                                                  └──→ Stop (GTFS)
```

## Use Cases

### 1. Driver Assignment
```python
# Assign driver to run
assignment = RosterAssignments.objects.create(
    operator=driver,
    run=run,
    assignment_date='2025-11-25'
)
```

### 2. View Operator Schedule
```bash
GET /api/tods/roster-assignments/?operator=123&assignment_date=2025-11-25
```

### 3. Track Deadhead Movements
```bash
GET /api/tods/deadheads/?service=weekday
GET /api/tods/deadhead-stop-times/?deadhead=DH001
```

### 4. Monitor Run Events
```bash
GET /api/tods/run-events/?run=RUN001&event_type=0
```

## API Examples

### List Operators
```bash
curl -X GET http://localhost:8000/api/tods/operators/ \
  -H "Authorization: Bearer <token>"
```

**Response**:
```json
[
  {
    "operator_id": "OP001",
    "operator_type": 0,
    "operator_name": "John Doe",
    "operator_phone": "+506-1234-5678",
    "operator_license_no": "CR-12345"
  }
]
```

### Get Run Details
```bash
curl -X GET http://localhost:8000/api/tods/runs/RUN001/ \
  -H "Authorization: Bearer <token>"
```

**Response**:
```json
{
  "run_id": "RUN001",
  "route": "1",
  "service": "weekday",
  "start_type": 0,
  "end_type": 1,
  "run_pieces": [
    {
      "piece_type": 0,
      "trip": "TRIP123",
      "start_time": "06:00:00",
      "end_time": "08:00:00",
      "piece_sequence": 1
    }
  ]
}
```

### Filter Roster Assignments
```bash
curl -X GET "http://localhost:8000/api/tods/roster-assignments/?operator=OP001&assignment_date=2025-11-25" \
  -H "Authorization: Bearer <token>"
```

## Database Tables

- `tods_operators`
- `tods_runs`
- `tods_run_pieces`
- `tods_run_events`
- `tods_deadheads`
- `tods_deadhead_stop_times`
- `tods_roster_assignments`

## Migrations

Created and applied successfully:
- `tods/migrations/0001_initial.py`

## Integration with GTFS

TODS extends GTFS by:
- Linking to GTFS `Route` and `Trip`
- Using GTFS `Calendar` for service periods
- Referencing GTFS `Stop` for locations
- Maintaining GTFS foreign key relationships

## Benefits

1. **Operational Planning**: Schedule operator duties and runs
2. **Resource Management**: Track driver and vehicle assignments
3. **Compliance**: Record operational events and breaks
4. **Optimization**: Analyze deadhead movements
5. **Real-time Operations**: Monitor operator assignments dynamically

## Testing

### Run TODS Tests
```bash
pytest tods/tests.py -v
```

### Model Tests
- Operator creation
- Run creation with route/service
- Run piece relationships
- Run event sequencing
- Deadhead with stop times
- Roster assignments

### API Tests
- List endpoints
- Detail endpoints
- Filtering
- Relationships

## Documentation

- TODS README: `tods/README.md`
- This summary document
- API docs included in OpenAPI schema

## Acceptance Criteria Status

✅ TODS models implemented (7 models)  
✅ API endpoints created (7 resources)  
✅ GTFS integration (foreign keys)  
✅ Django admin interface  
✅ Serializers for all models  
✅ URL routing configured  
✅ Tests implemented (14 tests)  
✅ Documentation created  

## Related Issues

- ✅ Issue #18: CRUD Endpoints (TODS endpoints included)
- ✅ Issue #21: JWT Authentication (secures TODS endpoints)
- ✅ Issue #26: Testing (TODS tests included)

## Known Issues

None identified.

## Future Enhancements

- Real-time roster assignment updates via WebSocket
- Integration with GPS tracking for run monitoring
- Automated run piece optimization
- Driver performance metrics
- Vehicle maintenance scheduling

## References

- [TODS Specification](https://github.com/TODS-Spec/TODS)
- [GTFS Reference](https://gtfs.org/)
- TODS README: `tods/README.md`

## Conclusion

**Issue #16 is COMPLETE**. TODS (Transit Operational Data Standard) is fully integrated into Databus API with 7 models, 7 API endpoints, comprehensive tests, and documentation. The implementation extends GTFS with operational data for driver assignments, runs, deadheads, and roster management.
