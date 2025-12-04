# Documentación del Proyecto

## Endpoint

La API de GraphQL está disponible en:

```
/graphql/
```
### Método de Autenticación

1. **Session Authentication** - Para acceso desde navegador web
2. **Token Authentication** - Para clientes API (vía DRF Token Auth)

### Ejemplo con Autenticación por Token

```bash
curl -X POST http://localhost:8000/graphql/ \
  -H "Authorization: Token YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ allFeeds { id name } }"}'
```

## Permisos

- **Queries**: Requieren autenticación (cualquier usuario autenticado)
- **Mutations**: Requieren permisos de staff (`is_staff=True`)

## Ejecutar el Endpoint de GraphQL

### Desarrollo

1. Iniciar el servidor de desarrollo de Django:

```bash
python manage.py runserver
```

2. Ingrese a `http://localhost:8000/graphql/` en su navegador para acceder a la interfaz GraphiQL.


## Descripción General del Esquema

### Tipos

- **FeedType**: Representa un feed GTFS
- **AgencyType**: Agencias de transporte
- **RouteType**: Rutas de transporte
- **StopType**: Paradas/estaciones de transporte
- **TripType**: Viajes individuales
- **StopTimeType**: Horarios de paradas para viajes
- **CalendarType**: Calendarios de servicio

### Paginación

La mayoría de las consultas de listas devuelven resultados paginados con la siguiente estructura:

```graphql
type Connection {
  edges: [Type!]!
  pageInfo: PageInfo!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
  totalCount: Int!
}
```

## Ejemplos de Consultas

### 1. Obtener Todos los Feeds

```graphql
query {
  allFeeds {
    id
    name
    url
    createdAt
    updatedAt
  }
}
```

### 2. Obtener un Feed por ID

```graphql
query {
  feed(id: 1) {
    id
    name
    url
  }
}
```

### 3. Obtener Todas las Agencias (con Paginación)

```graphql
query {
  allAgencies(offset: 0, limit: 20) {
    edges {
      id
      agencyName
      agencyUrl
      agencyTimezone
      agencyLang
      feed {
        name
      }
    }
    pageInfo {
      totalCount
      hasNextPage
      hasPreviousPage
    }
  }
}
```

### 4. Filtrar Agencias por Nombre

```graphql
query {
  allAgencies(nameContains: "Metro") {
    edges {
      agencyName
      agencyUrl
    }
    pageInfo {
      totalCount
    }
  }
}
```

### 5. Obtener Rutas con Filtros

```graphql
query {
  allRoutes(routeType: 3, shortNameContains: "1") {
    edges {
      routeShortName
      routeLongName
      routeType
      routeColor
      agency {
        agencyName
      }
    }
    pageInfo {
      totalCount
    }
  }
}
```

**Route Types:**
- `0`: Odontología
- `1`: Educación
- `2`: Ingeniería
- `3`: Ciencias del Movimiento Humano
- `4`: Ciencias Sociales
- `5`: LANAMME
- `6`: Artes
- `7`: Microbiología

### 6. Obtener Paradas Cercanas a una Ubicación

```graphql
query {
  allStops(nameContains: "Station", offset: 0, limit: 10) {
    edges {
      stopName
      stopLat
      stopLon
      locationType
      wheelchairBoarding
    }
    pageInfo {
      totalCount
    }
  }
}
```

### 7. Obtener Viajes por Ruta

```graphql
query {
  tripsByRoute(routeId: 1, directionId: 0) {
    edges {
      tripId
      tripHeadsign
      directionId
      serviceId
      route {
        routeShortName
        routeLongName
      }
    }
    pageInfo {
      totalCount
    }
  }
}
```

### 8. Obtener Horarios de Paradas para un Viaje

```graphql
query {
  stopTimesByTrip(tripId: 1) {
    edges {
      stopSequence
      arrivalTimeStr
      departureTimeStr
      stop {
        stopName
        stopLat
        stopLon
      }
    }
    pageInfo {
      totalCount
    }
  }
}
```

### 9. Consulta Compleja Anidada

```graphql
query {
  trip(id: 1) {
    tripId
    tripHeadsign
    directionId
    route {
      routeShortName
      routeLongName
      agency {
        agencyName
        agencyTimezone
      }
    }
  }
}
```

## Ejemplos de Mutaciones

### 1. Crear una Nueva Agencia

```graphql
mutation {
  createAgency(
    input: {
      feedId: 1
      agencyId: "NYC_MTA"
      agencyName: "New York MTA"
      agencyUrl: "https://www.ticabus.info"
      agencyTimezone: "America/Costa Rica"
      agencyLang: "en"
      agencyPhone: "511"
      agencyEmail: "info@ticabus.info"
    }
  ) {
    success
    errors
    agency {
      id
      agencyName
      agencyUrl
      agencyTimezone
    }
  }
}
```

### 2. Crear Agencia con Campos Mínimos

```graphql
mutation {
  createAgency(
    input: {
      feedId: 1
      agencyId: "AGENCY_001"
      agencyName: "Transit Agency"
      agencyUrl: "https://transit.example.com"
      agencyTimezone: "UTC"
    }
  ) {
    success
    errors
    agency {
      id
      agencyName
    }
  }
}
```

### 3. Manejar Errores de Validación

```graphql
mutation {
  createAgency(
    input: {
      feedId: 999  # Feed inexistente
      agencyId: "TEST"
      agencyName: ""  # Nombre vacío (inválido)
      agencyUrl: "https://test.com"
      agencyTimezone: "America/CostaRica"
    }
  ) {
    success
    errors
    agency {
      agencyName
    }
  }
}
```

**Respuesta:**
```json
{
  "data": {
    "createAgency": {
      "success": false,
      "errors": [
        "Agency name is required and cannot be empty",
        "Feed with id 999 does not exist"
      ],
      "agency": null
    }
  }
}
```

## Usar Variables

Para consultas dinámicas, usar variables de GraphQL:

```graphql
query GetAgency($id: Int!) {
  agency(id: $id) {
    agencyName
    agencyUrl
  }
}
```

**Variables:**
```json
{
  "id": 1
}
```

## Patrones de Paginación

### Paginación Basada en Offset

La API usa paginación basada en offset (no basada en cursor):

```graphql
# Primera página (elementos 0-19)
query {
  allAgencies(offset: 0, limit: 20) {
    edges { ... }
    pageInfo {
      totalCount
      hasNextPage
    }
  }
}

# Segunda página (elementos 20-39)
query {
  allAgencies(offset: 20, limit: 20) {
    edges { ... }
    pageInfo {
      totalCount
      hasNextPage
    }
  }
}
```

**Límites Predeterminados:**
- La mayoría de consultas: `limit=20` (máx: `100`)
- Horarios de paradas: `limit=100` (máx: `200`)

## Manejo de Errores

### Errores de Autenticación

```json
{
  "errors": [
    {
      "message": "User is not authenticated",
      "path": ["allAgencies"]
    }
  ]
}
```

### Errores de Permisos

```json
{
  "errors": [
    {
      "message": "User must be staff to perform this operation",
      "path": ["createAgency"]
    }
  ]
}
```

### Errores de Validación

Las mutaciones devuelven mensajes de error estructurados:

```json
{
  "data": {
    "createAgency": {
      "success": false,
      "errors": [
        "Agency name is required and cannot be empty",
        "Agency URL is required and cannot be empty"
      ],
      "agency": null
    }
  }
}
```

## Extender el Esquema

### Agregar una Nueva Consulta

1. Definir la consulta en `graphql_api/queries.py`:

```python
@strawberry.field(permission_classes=[IsAuthenticated])
def my_custom_query(self, info: Info, param: str) -> List[MyType]:
    """Descripción de consulta personalizada"""
    return MyModel.objects.filter(field=param)
```

2. La consulta estará disponible automáticamente:

```graphql
query {
  myCustomQuery(param: "value") {
    field1
    field2
  }
}
```

### Agregar una Nueva Mutación

1. Definir el tipo de entrada en `graphql_api/types.py`:

```python
@strawberry.input
class CreateMyEntityInput:
    name: str
    description: Optional[str] = None

@strawberry.type
class CreateMyEntityPayload:
    entity: Optional[MyEntityType]
    errors: list[str]
    success: bool
```

2. Definir la mutación en `graphql_api/mutations.py`:

```python
@strawberry.mutation(permission_classes=[IsStaff])
def create_my_entity(
    self, info: Info, input: CreateMyEntityInput
) -> CreateMyEntityPayload:
    """Descripción de la mutación"""
    # Implementación
    pass
```

### Agregar un Nuevo Tipo

1. Definir el tipo en `graphql_api/types.py`:

```python
@strawberry.django.type
class MyEntityType:
    """Tipo GraphQL para el modelo MyEntity"""
    
    id: auto
    name: str
    description: Optional[str]
    created_at: datetime.datetime
```

2. Usarlo en consultas y mutaciones.

## Pruebas

Ejecutar las pruebas de GraphQL:

```bash
# Todas las pruebas de GraphQL
pytest tests/test_graphql/

# Archivo de prueba específico
pytest tests/test_graphql/test_queries.py

# Prueba específica
pytest tests/test_graphql/test_queries.py::TestQueries::test_all_agencies_query

# Con cobertura
pytest tests/test_graphql/ --cov=graphql_api
```

### Estructura de Pruebas

```
tests/test_graphql/
├── __init__.py
├── conftest.py          # Fixtures para las pruebas
├── test_schema.py       # Pruebas de estructura del esquema
├── test_queries.py      # Pruebas de funcionalidad de consultas
├── test_mutations.py    # Pruebas de mutaciones
└── test_permissions.py  # Pruebas de control de acceso
```

## Mejores Prácticas

### 1. Usar Paginación

Siempre usar paginación para consultas de listas para evitar problemas de rendimiento:

```graphql
# ✅ Bien
query {
  allStops(offset: 0, limit: 50) {
    edges { ... }
    pageInfo { totalCount }
  }
}

# ❌ Evitar (aún paginará con valores predeterminados, pero menos explícito)
query {
  allStops {
    edges { ... }
  }
}
```

### 2. Solicitar Solo los Campos Necesarios

GraphQL permite solicitar exactamente lo que necesitas:

```graphql
# ✅ Bien - Solo solicitar campos necesarios
query {
  allAgencies {
    edges {
      agencyName
      agencyUrl
    }
  }
}

# ❌ Menos eficiente - Solicitar todos los campos
query {
  allAgencies {
    edges {
      id
      agencyId
      agencyName
      agencyUrl
      agencyTimezone
      agencyLang
      agencyPhone
      agencyFareUrl
      agencyEmail
      feed { ... }
    }
  }
}
```

### 3. Usar Variables para Consultas Dinámicas

```graphql
# ✅ Bien - Usar variables
query GetRoute($id: Int!) {
  route(id: $id) {
    routeShortName
  }
}

# ❌ Evitar - Interpolación de cadenas (riesgo de seguridad)
query {
  route(id: ${userInput}) {
    routeShortName
  }
}
```

### 4. Manejar Errores Correctamente

Siempre verificar tanto errores de GraphQL como errores de mutaciones:

```javascript
const result = await fetch('/graphql/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Token ${token}`
  },
  body: JSON.stringify({ query })
});

const data = await result.json();

// Verificar errores de GraphQL
if (data.errors) {
  console.error('Errores de GraphQL:', data.errors);
}

// Verificar errores de mutación
if (data.data?.createAgency?.errors?.length > 0) {
  console.error('Mutation errors:', data.data.createAgency.errors);
}
```

## Ejemplos de Integración

### Cliente Python

```python
import requests

GRAPHQL_URL = "http://localhost:8000/graphql/"
TOKEN = "your-auth-token"

def query_agencies():
    query = """
    query {
        allAgencies(limit: 10) {
            edges {
                agencyName
                agencyUrl
            }
            pageInfo {
                totalCount
            }
        }
    }
    """
    
    response = requests.post(
        GRAPHQL_URL,
        json={"query": query},
        headers={"Authorization": f"Token {TOKEN}"}
    )
    
    return response.json()

result = query_agencies()
print(result["data"]["allAgencies"])
```

### Cliente JavaScript

```javascript
async function createAgency(feedId, agencyData) {
  const mutation = `
    mutation CreateAgency($input: CreateAgencyInput!) {
      createAgency(input: $input) {
        success
        errors
        agency {
          id
          agencyName
        }
      }
    }
  `;

  const variables = {
    input: {
      feedId: feedId,
      ...agencyData
    }
  };

  const response = await fetch('/graphql/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Token ${yourToken}`
    },
    body: JSON.stringify({ query: mutation, variables })
  });

  const result = await response.json();
  
  if (result.data.createAgency.success) {
    console.log('Agencia creada:', result.data.createAgency.agency);
  } else {
    console.error('Errores:', result.data.createAgency.errors);
  }
}
```

## Solución de Problemas

### Problema: "User is not authenticated"

**Solución:** Asegurarse de pasar las credenciales de autenticación:

```bash
# Con token
curl -H "Authorization: Token YOUR_TOKEN" ...

# Con sesión (navegador)
# Asegurarse de iniciar sesión primero
```

### Problema: "User must be staff to perform this operation"

**Solución:** Las mutaciones requieren permisos de staff. Actualizar usuario:

```python
user.is_staff = True
user.save()
```

### Problema: Consultas Lentas

**Solución:** 
1. Usar paginación con tamaños de página más pequeños
2. Solicitar solo los campos necesarios
3. Agregar índices de base de datos en campos filtrados frecuentemente

### Problema: No se Puede Encontrar Tipo/Campo

**Solución:** Verificar el explorador de documentación de la interfaz GraphiQL para ver los tipos y campos disponibles.

## Recursos Adicionales

- [Documentación de Strawberry GraphQL](https://strawberry.rocks/docs)
- [Documentación Oficial de GraphQL](https://graphql.org/)
- [Especificación GTFS](https://gtfs.org/schedule/reference/)
- [Autenticación de Django](https://docs.djangoproject.com/en/stable/topics/auth/)

## Soporte

Para problemas o preguntas:
1. Verificar la documentación de la interfaz GraphiQL
2. Revisar los archivos de prueba en `tests/test_graphql/`
3. Consultar la documentación de Strawberry GraphQL
4. Abrir un issue en el repositorio del proyecto
