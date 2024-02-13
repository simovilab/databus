# Especificación del API

# APIs

- Publicar datos en tiempo real 
(requiere autenticación)
```http
POST /api/datos {"vehicle_id": ...}
```

- Obtener GTFS Schedule
(no requiere autenticación)
```http
GET /api/gtfs
```

- Obtener GTFS Realtime - Actualizaciones de viaje (`TripUpdates`)
```http
GET /api/realtime/trip-updates
```

- Obtener GTFS Realtime - Posiciones del vehículo (`VehiclePositions`)
```http
GET /api/realtime/vehicle-positions
```


`bus.ucr.ac.cr/api/datos`

## Especificación de los datos de los vehículos

La siguiente especificación de datos fue construida con base en:

- La especificación de datos abiertos de transporte público GTFS Schedule y GTFS Realtime v2.0
- La Arquitectura de Referencia para Transporte Inteligente y Colaborativo (ARC-IT) del Departamento de Transportes de los Estados Unidos

Su objetivo primario es la construcción de un *feed* (o "suministro de datos") en tiempo real para consumo de aplicaciones compatibles con GTFS. Esto es de utilidad, especialmente, para usuarios del servicio.

Pero también está diseñado para prever necesidades y aplicaciones futuras con base en la amplia especificación de "paquetes de servicio" para transporte público de ARC-IT. Esto podría de uso primario para operadores, gestores, planificadores, reguladores y otras partes interesadas.

```json
{
    "vehicle_id": "1234",
    "route_id": "bUCR_L1",
    "trip_id": "EYU94JE743",
    "location": {
        "latitude": 9.98363,
        "longitude": -84.9474573
    }
}
```