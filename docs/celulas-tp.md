# Proyecto Células TP: Buses como Sensores Rodantes

## Introducción

El concepto de "Células TP" (Transporte Público) propone utilizar los buses como **sensores rodantes** que recopilan datos de telemetría, rastreo y condiciones ambientales mientras realizan sus rutas regulares. Esta infraestructura de "computación móvil" convierte la flota de transporte público en una red de sensores distribuida que puede proporcionar información valiosa sobre:

- **Movilidad urbana**: Patrones de tráfico, congestión, tiempos de viaje
- **Calidad del servicio**: Ocupación, puntualidad, cobertura
- **Condiciones ambientales**: Calidad del aire, temperatura, humedad
- **Infraestructura vial**: Estado de carreteras, eventos en tiempo real

## Compatibilidad con Databus

El proyecto Databus está diseñado para ser la **plataforma central** que recibe, procesa y distribuye los datos generados por estas "células móviles":

### Arquitectura Compatible

```
┌─────────────────┐
│  Buses (Células)│
│  - GPS          │
│  - Sensores     │
│  - Telemetría   │
└────────┬────────┘
         │ GTFS Realtime
         │ HTTP/WebSocket
         ▼
┌─────────────────┐
│  Databus API    │
│  - Position     │
│  - Occupancy    │
│  - Emissions    │
│  - Conditions   │
└────────┬────────┘
         │ REST API
         │ GTFS-RT Feed
         │ NGSI-LD (futuro)
         ▼
┌─────────────────┐
│  Aplicaciones   │
│  - Dashboards   │
│  - Análisis     │
│  - Smart City   │
└─────────────────┘
```

### Endpoints API Disponibles

Databus proporciona los siguientes endpoints para recibir datos de las células:

1. **Vehicle** (`/api/vehicle/`)
   - Información del vehículo
   - Identificación de la célula móvil

2. **Equipment** (`/api/equipment/`)
   - Capacidades del equipo instalado
   - Tipos de sensores disponibles

3. **Journey** (`/api/journey/`)
   - Viaje actual del bus
   - Ruta y horario

4. **Position** (`/api/position/`)
   - Ubicación GPS en tiempo real
   - Velocidad, dirección, odómetro
   - **Actualización**: Cada 10 segundos

5. **Progression** (`/api/progression/`)
   - Progreso en la ruta
   - Estado en paradas
   - Nivel de congestión

6. **Occupancy** (`/api/occupancy/`)
   - Ocupación del vehículo
   - Conteo de pasajeros
   - **Actualización**: En cada parada

7. **Emissions** (`/api/emissions/`)
   - Datos ambientales
   - Emisiones del vehículo
   - Calidad del aire

8. **Conditions** (`/api/conditions/`)
   - Condiciones operacionales
   - Temperatura, humedad
   - Estado del vehículo

### Frecuencia de Actualización

El sistema soporta diferentes intervalos según el tipo de dato:

| Tipo de Dato | Frecuencia Recomendada | Endpoint |
|--------------|------------------------|----------|
| Position | 10 segundos | `/api/position/` |
| Occupancy | Al llegar a parada | `/api/occupancy/` |
| Emissions | 30-60 segundos | `/api/emissions/` |
| Conditions | 60 segundos | `/api/conditions/` |
| Progression | Al cambiar estado | `/api/progression/` |

## Simulador como Prototipo

El **simulador de telemetría** implementado en `simulator/` permite probar el concepto de "Células TP" antes de desplegar equipos reales:

### Características del Simulador

1. **Simula células móviles completas**:
   - Vehículos con equipos de telemetría
   - Movimiento a lo largo de rutas GTFS
   - Generación de datos realistas

2. **Envía datos periódicos**:
   - Position cada 10 segundos
   - Occupancy en cada parada
   - Progression según avance en ruta

3. **Implementado con Celery Beat**:
   - Tareas periódicas programadas
   - Escalable a múltiples vehículos
   - Monitoreo y logging completo

### Flujo de Simulación

```python
# 1. Iniciar simulación
docker-compose exec web python manage.py start_simulation --all

# 2. Celery Beat ejecuta cada 10 segundos
@shared_task(name='simulator.update_positions')
def update_simulated_positions():
    # Para cada vehículo activo:
    # - Actualizar posición siguiendo shape points
    # - Detectar llegada a paradas
    # - Actualizar ocupación
    # - Registrar eventos

# 3. Datos disponibles en API
GET /api/position/
GET /api/journey/
GET /api/occupancy/
```

### Validación del Concepto

El simulador permite validar:

1. **Rendimiento de la API**:
   - ¿Puede manejar múltiples buses enviando datos simultáneamente?
   - ¿Los tiempos de respuesta son aceptables?

2. **Generación de GTFS Realtime**:
   - ¿Los datos se convierten correctamente a feed GTFS-RT?
   - ¿Las aplicaciones cliente pueden consumir el feed?

3. **Integración con sistemas externos**:
   - Dashboards de visualización
   - Sistemas de información al pasajero
   - Plataformas de Smart City

4. **Escalabilidad**:
   - Probar con 1, 10, 100+ vehículos simulados
   - Identificar cuellos de botella
   - Optimizar antes del despliegue real

## Casos de Uso

### 1. Información al Pasajero en Tiempo Real

Los datos de Position y Progression permiten:
- Mostrar buses en mapas en tiempo real
- Calcular tiempos de llegada estimados
- Notificar retrasos o desvíos

### 2. Optimización de Rutas

Los datos históricos de Position y Conditions permiten:
- Identificar zonas de congestión recurrente
- Optimizar horarios según patrones reales
- Ajustar frecuencias según demanda (Occupancy)

### 3. Monitoreo Ambiental

Los datos de Emissions y Conditions permiten:
- Mapear calidad del aire en la ciudad
- Identificar zonas con problemas ambientales
- Correlacionar tráfico con contaminación

### 4. Mantenimiento Predictivo

Los datos de telemetría del vehículo permiten:
- Detectar patrones de fallo
- Programar mantenimiento preventivo
- Reducir costos operativos

## Preparación para Despliegue Real

### 1. Requisitos de Hardware

Cada "célula" (bus) necesita:

- **Equipo GPS**: Para Position
  - Actualización 1 Hz (1 vez por segundo)
  - Precisión < 5 metros

- **Contadores de pasajeros**: Para Occupancy
  - Sensores en puertas
  - Algoritmos de conteo

- **Sensores ambientales** (opcional): Para Emissions/Conditions
  - CO₂, NOx, PM2.5
  - Temperatura, humedad

- **Unidad de comunicación**:
  - Conexión 4G/5G
  - Buffer para datos offline
  - Protocolo HTTP/MQTT

### 2. Software en el Bus

```python
# Pseudocódigo del cliente en el bus
import requests
from datetime import datetime

API_URL = "https://databus.example.com/api"
TOKEN = "your-auth-token"

def send_position():
    data = {
        "journey": current_journey_id,
        "vehicle": vehicle_id,
        "timestamp": datetime.now().isoformat(),
        "latitude": gps.get_lat(),
        "longitude": gps.get_lon(),
        "speed": gps.get_speed(),
        "bearing": gps.get_bearing()
    }
    
    response = requests.post(
        f"{API_URL}/position/",
        json=data,
        headers={"Authorization": f"Token {TOKEN}"}
    )
    
    return response.status_code == 201

# Ejecutar cada 10 segundos
while True:
    send_position()
    time.sleep(10)
```

### 3. Seguridad

- **Autenticación**: Token por vehículo
- **Encriptación**: HTTPS para todas las comunicaciones
- **Rate limiting**: Prevenir abuso de la API
- **Validación**: Verificar datos antes de almacenar

### 4. Escalabilidad

Para una flota de 100+ buses:

- **Base de datos**: PostgreSQL con TimescaleDB para series temporales
- **Caché**: Redis para datos en tiempo real
- **Cola de tareas**: Celery para procesamiento asíncrono
- **Balanceo de carga**: Nginx + múltiples instancias de Django
- **Almacenamiento**: Archivar datos históricos (S3/MinIO)

## Integración con NGSI-LD

El documento [`docs/ngsi-ld-compatibility.md`](ngsi-ld-compatibility.md) describe cómo integrar Databus con el estándar NGSI-LD para:

- Interoperabilidad con plataformas Smart City
- Contexto semántico para los datos
- Federación con otros sistemas

Ejemplo de entidad NGSI-LD para una célula:

```json
{
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
    "https://smartdatamodels.org/context.jsonld"
  ],
  "id": "urn:ngsi-ld:Vehicle:SJB9876",
  "type": "Vehicle",
  "category": {
    "type": "Property",
    "value": ["publicTransport", "bus"]
  },
  "location": {
    "type": "GeoProperty",
    "value": {
      "type": "Point",
      "coordinates": [-84.0833, 9.9333]
    }
  },
  "speed": {
    "type": "Property",
    "value": 45.5,
    "unitCode": "KMH"
  },
  "occupancyLevel": {
    "type": "Property",
    "value": 0.67,
    "observedAt": "2025-11-25T10:30:00Z"
  },
  "emissions": {
    "type": "Property",
    "value": {
      "CO2": 150,
      "NOx": 0.5
    },
    "unitCode": "GPM"
  }
}
```

## Cronograma de Implementación

### Fase 1: Simulación (Actual)
- ✅ Simulador implementado
- ✅ API endpoints funcionales
- ✅ Generación GTFS Realtime
- 🔄 Pruebas de carga
- 🔄 Validación con stakeholders

### Fase 2: Piloto (3-6 meses)
- Equipar 5-10 buses con hardware real
- Desarrollar software embebido
- Implementar monitoreo y alertas
- Recopilar feedback operacional

### Fase 3: Despliegue Gradual (6-12 meses)
- Equipar 50% de la flota
- Optimizar basado en datos reales
- Integrar con sistemas existentes
- Capacitar operadores

### Fase 4: Despliegue Completo (12-18 meses)
- Equipar 100% de la flota
- Habilitar casos de uso avanzados
- Integración NGSI-LD completa
- Apertura de datos a terceros

## Beneficios Esperados

### Para el Operador
- Mejor visibilidad de la flota
- Optimización de rutas y horarios
- Reducción de costos operativos
- Mantenimiento predictivo

### Para los Pasajeros
- Información en tiempo real confiable
- Mejor experiencia de viaje
- Planificación más efectiva

### Para la Ciudad
- Datos para planificación urbana
- Monitoreo ambiental continuo
- Mejor gestión del tráfico
- Infraestructura Smart City

## Referencias

- [Documentación del Simulador](simulator.md)
- [Compatibilidad NGSI-LD](ngsi-ld-compatibility.md)
- [Documentación del API](api.md)
- [GTFS Realtime Specification](https://gtfs.org/realtime/)
- [ETSI NGSI-LD Standard](https://www.etsi.org/deliver/etsi_gs/CIM/001_099/009/01.08.01_60/gs_CIM009v010801p.pdf)

## Contacto

Para más información sobre el Proyecto Células TP y su implementación con Databus, contactar al equipo de desarrollo.
