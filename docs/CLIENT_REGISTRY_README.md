# API Client Registry and Lifecycle Management



## Descripción

Sistema completo de gestión de registro y ciclo de vida de clientes API con autenticación mediante claves, cuotas de uso, seguimiento de estado y métricas.

## Modelos

### 1. APIClient
Representa un cliente API registrado con autenticación y gestión de cuotas.

**Campos principales:**
- `client_id`: Identificador único del cliente (generado automáticamente)
- `client_name`: Nombre descriptivo
- `client_type`: Tipo de cliente (vehicle, device, user, agency, integration)
- `owner`: Usuario propietario
- `status`: Estado actual (pending, active, suspended, disabled, revoked)
- `allowed_ips`: Lista de IPs permitidas (opcional)
- `metadata`: Metadata adicional (JSON)

**Métodos del ciclo de vida:**
- `activate()`: Aprobar y activar cliente
- `suspend()`: Suspender cliente temporalmente
- `disable()`: Deshabilitar cliente
- `revoke()`: Revocar cliente permanentemente

### 2. APIKey
Claves API para autenticación de clientes con soporte para rotación.

**Características:**
- Generación segura de claves con `secrets` module
- Hash SHA-256 para almacenamiento seguro
- Expiración configurable
- Seguimiento de último uso
- Rotación de claves

**Métodos principales:**
- `create_key()`: Crear nueva clave
- `verify_key()`: Verificar clave secreta
- `is_valid()`: Verificar si la clave está activa y no expiró
- `revoke()`: Revocar clave
- `rotate()`: Rotar clave (crear nueva y revocar actual)

### 3. ClientQuota
Cuotas y límites de uso para clientes API.

**Límites configurables:**
- Solicitudes por minuto/hora/día
- Puntos de datos máximos por solicitud
- Conexiones WebSocket concurrentes
- Permisos de escritura
- Acceso a datos en tiempo real e históricos

### 4. ClientUsageMetrics
Métricas de uso de clientes API por períodos (hora/día/mes).

**Métricas capturadas:**
- Total de solicitudes (exitosas/fallidas)
- Puntos de datos leídos/escritos
- Tiempos de respuesta (promedio/máximo)
- Violaciones de cuota
- Ancho de banda (bytes enviados/recibidos)
- Conexiones y mensajes WebSocket

### 5. ClientAuditLog
Registro de auditoría de eventos de ciclo de vida y acciones administrativas.

**Eventos registrados:**
- Creación/aprobación/activación de clientes
- Suspensión/deshabilitación/revocación
- Creación/rotación/revocación de claves
- Actualizaciones de cuota
- Excesos de cuota
- Bloqueos de IP

## API REST Endpoints

### Clients
- `GET /api/clients/` - Listar clientes (propios o todos si admin)
- `POST /api/clients/` - Registrar nuevo cliente
- `GET /api/clients/{client_id}/` - Obtener detalles de cliente
- `PATCH /api/clients/{client_id}/` - Actualizar cliente
- `DELETE /api/clients/{client_id}/` - Eliminar cliente

### Lifecycle Management
- `POST /api/clients/{client_id}/lifecycle/` - Ejecutar acción de ciclo de vida
  ```json
  {
    "action": "approve|activate|suspend|disable|revoke",
    "reason": "Motivo (opcional)"
  }
  ```

### Quota Management
- `GET /api/clients/{client_id}/quota/` - Obtener cuota del cliente
- `PATCH /api/clients/{client_id}/update_quota/` - Actualizar cuota (admin)

### API Keys
- `GET /api/clients/{client_id}/keys/` - Listar claves del cliente
- `POST /api/clients/{client_id}/create_key/` - Crear nueva clave
  ```json
  {
    "name": "Nombre de la clave",
    "expires_in_days": 365
  }
  ```
- `POST /api/clients/{client_id}/keys/{key_id}/revoke/` - Revocar clave
- `POST /api/clients/{client_id}/keys/{key_id}/rotate/` - Rotar clave

### Metrics & Audit
- `GET /api/clients/{client_id}/metrics/` - Obtener métricas de uso
- `GET /api/clients/{client_id}/audit_log/` - Obtener registro de auditoría
- `GET /api/client-metrics/` - Listar todas las métricas
- `GET /api/client-audit/` - Listar todos los logs de auditoría

## Interfaz de Administración Django

### APIClient Admin
- Vista de lista con filtros por estado y tipo
- Acciones en lote: aprobar, suspender, activar, revocar
- Badges de estado con colores
- Estadísticas de uso
- Inlines para: cuotas, claves API, logs de auditoría

### APIKey Admin
- Visualización de prefijo de clave (solo primeros 8 caracteres)
- Estado de activación y expiración
- Fecha de último uso
- Acción de revocación

### ClientQuota Admin
- Edición de todos los límites de tasa
- Configuración de características
- Umbrales de advertencia

### ClientUsageMetrics Admin
- Solo lectura
- Filtros por período
- Tasa de éxito calculada
- Vista de métricas de rendimiento

### ClientAuditLog Admin
- Solo lectura (no eliminable)
- Filtros por tipo de evento
- Búsqueda por cliente/usuario/IP
- Vista completa de metadata

## Flujo de Trabajo

### 1. Registro de Cliente

```bash
POST /api/clients/
{
  "client_name": "Bus 101 GPS Device",
  "client_type": "vehicle",
  "organization": "Transit Company A",
  "contact_email": "tech@transit-a.com",
  "description": "GPS device for bus 101",
  "metadata": {
    "vehicle_id": "BUS-101",
    "device_serial": "GPS123456"
  }
}
```

**Respuesta:** Cliente creado en estado `pending`

### 2. Aprobación (Admin)

```bash
POST /api/clients/{client_id}/lifecycle/
{
  "action": "approve"
}
```

**Resultado:** Cliente cambia a estado `active`

### 3. Creación de Clave API

```bash
POST /api/clients/{client_id}/create_key/
{
  "name": "Production Key",
  "expires_in_days": 365
}
```

**Respuesta:**
```json
{
  "message": "API key created successfully...",
  "key": {
    "key_id": "key_xxx",
    "key_display": "xxxxxxxx********",
    "name": "Production Key",
    "is_active": true,
    "expires_at": "2025-11-25T..."
  },
  "secret_key": "GUARDA_ESTA_CLAVE_DE_FORMA_SEGURA"
}
```

⚠️ **Importante:** La clave secreta solo se muestra una vez

### 4. Uso de la Clave

Los clientes usan la clave API en sus solicitudes:

```bash
curl -H "Authorization: ApiKey {secret_key}" \
     https://api.databus.com/api/positions/
```

### 5. Monitoreo

**Ver métricas:**
```bash
GET /api/clients/{client_id}/metrics/?period_type=day&days=7
```

**Ver auditoría:**
```bash
GET /api/clients/{client_id}/audit_log/?limit=50
```

### 6. Rotación de Clave

```bash
POST /api/clients/{client_id}/keys/{key_id}/rotate/
{
  "expires_in_days": 365
}
```

**Resultado:** Nueva clave creada, clave anterior revocada

### 7. Suspensión (si necesario)

```bash
POST /api/clients/{client_id}/lifecycle/
{
  "action": "suspend",
  "reason": "Actividad sospechosa detectada"
}
```

## Seguridad

### Almacenamiento de Claves
- Las claves nunca se almacenan en texto plano
- Se guarda solo el hash SHA-256
- La clave secreta se muestra una sola vez al crearla

### Autenticación
- Las claves API se verifican contra el hash almacenado
- Las claves expiradas se rechazan automáticamente
- Las claves revocadas no pueden usarse

### Control de Acceso
- Los usuarios solo ven sus propios clientes
- Los admins ven todos los clientes
- Solo los admins pueden aprobar/suspender/revocar

### Auditoría
- Todas las acciones del ciclo de vida se registran
- Se guarda quién realizó cada acción
- IP y user agent se capturan cuando están disponibles

## Cuotas y Límites

### Límites Predeterminados
```python
{
    'requests_per_minute': 60,
    'requests_per_hour': 1000,
    'requests_per_day': 10000,
    'max_data_points_per_request': 1000,
    'max_concurrent_connections': 5,
    'can_write': False,
    'can_subscribe_realtime': True,
    'can_access_historical': True,
}
```

### Personalización (Admin)
Los admins pueden ajustar los límites según el tipo de cliente y necesidades.

## Métricas

### Período Horario
- Granularidad de 1 hora
- Útil para detección de picos de uso

### Período Diario
- Resumen diario
- Para análisis de tendencias

### Período Mensual
- Consolidado mensual
- Para facturación y reportes

## Tipos de Cliente

1. **vehicle**: Dispositivos GPS en vehículos
2. **device**: Dispositivos genéricos
3. **user**: Aplicaciones de usuario final
4. **agency**: Sistemas de agencias de transporte
5. **integration**: Integraciones con terceros

## Estados del Ciclo de Vida

1. **pending**: Pendiente de aprobación
2. **active**: Activo y operacional
3. **suspended**: Suspendido temporalmente
4. **disabled**: Deshabilitado
5. **revoked**: Revocado permanentemente

## Próximos Pasos

### Mejoras Futuras
1. ✅ Modelos completos implementados
2. ✅ CRUD operations
3. ✅ Lifecycle management
4. ✅ Métricas de uso
5. ✅ Admin views
6. 🔄 Middleware de autenticación con APIKey
7. 🔄 Sistema de alertas de cuota
8. 🔄 Dashboard de métricas
9. 🔄 Exportación de reportes

### Testing
Ejecutar pruebas:
```bash
docker-compose exec web python manage.py test api.tests.test_clients
```

## Cumplimiento de Criterios de Aceptación

- ✅ **Models for clients, keys, quotas, status**: 5 modelos implementados
- ✅ **CRUD and lifecycle operations**: ViewSets completos con 15+ endpoints
- ✅ **Metrics of usage per client captured**: ClientUsageMetrics con 15+ métricas
- ✅ **Admin views for management**: 5 ModelAdmin con acciones en lote
