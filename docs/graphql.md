# GraphQL API Documentation

## Overview

The Databús GraphQL API provides a modern, flexible interface for querying and manipulating GTFS (General Transit Feed Specification) data. Built with [Strawberry GraphQL](https://strawberry.rocks/) and integrated into the Django framework, it offers:

- **Type-safe queries and mutations**
- **Pagination support** using offset-based pagination
- **Filtering capabilities** on most queries
- **Authentication and permission controls**
- **Interactive GraphiQL interface** for exploration

## Endpoint

The GraphQL API is available at:

```
/graphql/
```

## Authentication

All queries and mutations require authentication. The API uses Django's authentication system.

### Authentication Methods

1. **Session Authentication** - For web browser access
2. **Token Authentication** - For API clients (via DRF Token Auth)

### Example with Token Authentication

```bash
curl -X POST http://localhost:8000/graphql/ \
  -H "Authorization: Token YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ allFeeds { id name } }"}'
```

## Permissions

- **Queries**: Require authentication (any authenticated user)
- **Mutations**: Require staff permissions (`is_staff=True`)

## Running the GraphQL Endpoint

### Development

1. Start the Django development server:

```bash
python manage.py runserver
```

2. Navigate to `http://localhost:8000/graphql/` in your browser to access the GraphiQL interface.

### Using GraphiQL Interface

The GraphiQL interface provides:
- Auto-completion
- Schema documentation
- Query history
- Variable editor

## Schema Overview

### Types

- **FeedType**: Represents a GTFS feed
- **AgencyType**: Transit agencies
- **RouteType**: Transit routes
- **StopType**: Transit stops/stations
- **TripType**: Individual trips
- **StopTimeType**: Stop times for trips
- **CalendarType**: Service calendars

### Pagination

Most list queries return paginated results with the following structure:

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

## Query Examples

### 1. Get All Feeds

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

### 2. Get Single Feed by ID

```graphql
query {
  feed(id: 1) {
    id
    name
    url
  }
}
```

### 3. Get All Agencies (with Pagination)

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

### 4. Filter Agencies by Name

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

### 5. Get Routes with Filtering

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
- `0`: Tram/Light Rail
- `1`: Subway/Metro
- `2`: Rail
- `3`: Bus
- `4`: Ferry
- `5`: Cable Car
- `6`: Gondola
- `7`: Funicular

### 6. Get Stops Near Location

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

### 7. Get Trips by Route

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

### 8. Get Stop Times for a Trip

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

### 9. Complex Nested Query

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

## Mutation Examples

### 1. Create a New Agency

```graphql
mutation {
  createAgency(
    input: {
      feedId: 1
      agencyId: "NYC_MTA"
      agencyName: "New York MTA"
      agencyUrl: "https://www.mta.info"
      agencyTimezone: "America/New_York"
      agencyLang: "en"
      agencyPhone: "511"
      agencyEmail: "info@mta.info"
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

### 2. Create Agency with Minimal Fields

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

### 3. Handle Validation Errors

```graphql
mutation {
  createAgency(
    input: {
      feedId: 999  # Non-existent feed
      agencyId: "TEST"
      agencyName: ""  # Empty name (invalid)
      agencyUrl: "https://test.com"
      agencyTimezone: "America/New_York"
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

**Response:**
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

## Using Variables

For dynamic queries, use GraphQL variables:

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

## Pagination Patterns

### Offset-Based Pagination

The API uses offset-based pagination (not cursor-based):

```graphql
# First page (items 0-19)
query {
  allAgencies(offset: 0, limit: 20) {
    edges { ... }
    pageInfo {
      totalCount
      hasNextPage
    }
  }
}

# Second page (items 20-39)
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

**Default Limits:**
- Most queries: `limit=20` (max: `100`)
- Stop times: `limit=100` (max: `200`)

## Error Handling

### Authentication Errors

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

### Permission Errors

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

### Validation Errors

Mutations return structured error messages:

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

## Extending the Schema

### Adding a New Query

1. Define the query in `graphql_api/queries.py`:

```python
@strawberry.field(permission_classes=[IsAuthenticated])
def my_custom_query(self, info: Info, param: str) -> List[MyType]:
    """Custom query description"""
    return MyModel.objects.filter(field=param)
```

2. The query is automatically available:

```graphql
query {
  myCustomQuery(param: "value") {
    field1
    field2
  }
}
```

### Adding a New Mutation

1. Define input type in `graphql_api/types.py`:

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

2. Define mutation in `graphql_api/mutations.py`:

```python
@strawberry.mutation(permission_classes=[IsStaff])
def create_my_entity(
    self, info: Info, input: CreateMyEntityInput
) -> CreateMyEntityPayload:
    """Mutation description"""
    # Implementation
    pass
```

### Adding a New Type

1. Define type in `graphql_api/types.py`:

```python
@strawberry.django.type
class MyEntityType:
    """GraphQL type for MyEntity model"""
    
    id: auto
    name: str
    description: Optional[str]
    created_at: datetime.datetime
```

2. Use it in queries and mutations.

## Testing

Run the GraphQL tests:

```bash
# All GraphQL tests
pytest tests/test_graphql/

# Specific test file
pytest tests/test_graphql/test_queries.py

# Specific test
pytest tests/test_graphql/test_queries.py::TestQueries::test_all_agencies_query

# With coverage
pytest tests/test_graphql/ --cov=graphql_api
```

### Test Structure

```
tests/test_graphql/
├── __init__.py
├── conftest.py          # Fixtures for tests
├── test_schema.py       # Schema structure tests
├── test_queries.py      # Query functionality tests
├── test_mutations.py    # Mutation tests
└── test_permissions.py  # Access control tests
```

## Best Practices

### 1. Use Pagination

Always use pagination for list queries to avoid performance issues:

```graphql
# ✅ Good
query {
  allStops(offset: 0, limit: 50) {
    edges { ... }
    pageInfo { totalCount }
  }
}

# ❌ Avoid (will still paginate with defaults, but less explicit)
query {
  allStops {
    edges { ... }
  }
}
```

### 2. Request Only Needed Fields

GraphQL allows you to request exactly what you need:

```graphql
# ✅ Good - Only request needed fields
query {
  allAgencies {
    edges {
      agencyName
      agencyUrl
    }
  }
}

# ❌ Less efficient - Requesting all fields
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

### 3. Use Variables for Dynamic Queries

```graphql
# ✅ Good - Using variables
query GetRoute($id: Int!) {
  route(id: $id) {
    routeShortName
  }
}

# ❌ Avoid - String interpolation (security risk)
query {
  route(id: ${userInput}) {
    routeShortName
  }
}
```

### 4. Handle Errors Gracefully

Always check for both GraphQL errors and mutation errors:

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

// Check for GraphQL errors
if (data.errors) {
  console.error('GraphQL errors:', data.errors);
}

// Check for mutation errors
if (data.data?.createAgency?.errors?.length > 0) {
  console.error('Mutation errors:', data.data.createAgency.errors);
}
```

## Integration Examples

### Python Client

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

### JavaScript Client

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
    console.log('Agency created:', result.data.createAgency.agency);
  } else {
    console.error('Errors:', result.data.createAgency.errors);
  }
}
```

## Troubleshooting

### Issue: "User is not authenticated"

**Solution:** Ensure you're passing authentication credentials:

```bash
# With token
curl -H "Authorization: Token YOUR_TOKEN" ...

# With session (browser)
# Make sure you're logged in first
```

### Issue: "User must be staff to perform this operation"

**Solution:** Mutations require staff permissions. Update user:

```python
user.is_staff = True
user.save()
```

### Issue: Slow Queries

**Solution:** 
1. Use pagination with smaller page sizes
2. Request only needed fields
3. Add database indexes on frequently filtered fields

### Issue: Cannot Find Type/Field

**Solution:** Check the GraphiQL interface's documentation explorer to see available types and fields.

## Additional Resources

- [Strawberry GraphQL Documentation](https://strawberry.rocks/docs)
- [GraphQL Official Documentation](https://graphql.org/)
- [GTFS Specification](https://gtfs.org/schedule/reference/)
- [Django Authentication](https://docs.djangoproject.com/en/stable/topics/auth/)

## Support

For issues or questions:
1. Check the GraphiQL interface documentation
2. Review the test files in `tests/test_graphql/`
3. Consult the Strawberry GraphQL documentation
4. Open an issue in the project repository
