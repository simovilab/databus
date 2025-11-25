# NGSI-LD Compatibility Investigation

## Introduction

This document explores the potential compatibility between the Databus telemetry API and the NGSI-LD (Next Generation Service Interface with Linked Data) standard. The investigation is based on the FIWARE NGSI-LD tutorials and specifications to determine how our current OBE (On-Board Equipment) API could be adapted or extended to support NGSI-LD.

## What is NGSI-LD?

NGSI-LD is an API specification developed by ETSI (European Telecommunications Standards Institute) for managing context information. It builds upon JSON-LD (Linked Data) to enable interoperability across different systems and organizations. The latest specification version is 1.7.1, published in June 2023.

### Key Differences: NGSI-LD vs NGSI-v2

According to FIWARE, the choice between NGSI-LD and NGSI-v2 depends on your use case:

**NGSI-v2**
- Uses standard JSON format
- Suitable for individual smart systems
- Simpler to implement
- Good for isolated applications

**NGSI-LD**
- Uses JSON-LD format with @context
- Designed for federations and data spaces
- More complex but offers better interoperability
- Required for system-of-systems approaches

For the Databus project, NGSI-LD would be relevant if we plan to integrate with other transit systems, create data federations, or participate in smart city data spaces.

## Core NGSI-LD Concepts

### Context and @context

The @context is fundamental to NGSI-LD. It defines the vocabulary and data types used in your data model. This enables semantic interoperability because different systems can understand the meaning of data attributes.

Example of how a Vehicle entity might look in NGSI-LD:

```json
{
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
    "https://example.org/databus-context.jsonld"
  ],
  "id": "urn:ngsi-ld:Vehicle:SJB9876",
  "type": "Vehicle",
  "licenseplate": {
    "type": "Property",
    "value": "SJB 9876"
  },
  "location": {
    "type": "GeoProperty",
    "value": {
      "type": "Point",
      "coordinates": [-84.04392677465846, 9.937044983645931]
    }
  },
  "speed": {
    "type": "Property",
    "value": 12.5,
    "unitCode": "MTS",
    "observedAt": "2024-05-03T07:15:00Z"
  }
}
```

### Entity Relationships

NGSI-LD supports explicit relationships between entities using the "Relationship" type. This is more powerful than simple foreign keys because relationships are first-class citizens in the data model.

Example:
```json
{
  "id": "urn:ngsi-ld:Journey:698453",
  "type": "Journey",
  "vehicle": {
    "type": "Relationship",
    "object": "urn:ngsi-ld:Vehicle:SJB9876"
  },
  "operator": {
    "type": "Relationship",
    "object": "urn:ngsi-ld:Operator:1-1234-5678"
  }
}
```

### Temporal Representation

NGSI-LD has built-in support for temporal data, which is critical for our telemetry use case. Properties can have observedAt timestamps, and the specification supports querying historical data.

### Subscriptions and Notifications

Similar to our current API, NGSI-LD supports subscriptions where clients can be notified when entities change. This would map well to our real-time data streaming requirements.

## Current Databus API vs NGSI-LD

### Similarities

1. **Entity-Based Model**: Both APIs use entities (Vehicle, Journey, Position, etc.)
2. **Relationships**: Both support relationships between entities
3. **Real-time Updates**: Both support subscriptions and real-time data
4. **Geospatial Data**: Both handle geographic coordinates
5. **Temporal Data**: Both support timestamps for observations

### Differences

1. **Data Format**: 
   - Current: Standard JSON
   - NGSI-LD: JSON-LD with @context

2. **Property Structure**:
   - Current: `{"latitude": 9.937044}`
   - NGSI-LD: `{"latitude": {"type": "Property", "value": 9.937044}}`

3. **Entity IDs**:
   - Current: Simple strings or UUIDs
   - NGSI-LD: URNs following pattern `urn:ngsi-ld:EntityType:EntityId`

4. **Metadata**:
   - Current: Mixed with data
   - NGSI-LD: Explicit metadata structure

## Compatibility Assessment

### What Would Need to Change

1. **Entity ID Format**: Convert from simple IDs to URN format
   - Before: `"vehicle_id": "98E4TNSG"`
   - After: `"id": "urn:ngsi-ld:Vehicle:98E4TNSG"`

2. **Property Structure**: Wrap values in Property/GeoProperty/Relationship objects
   - Before: `"speed": 12.5`
   - After: `"speed": {"type": "Property", "value": 12.5}`

3. **Add @context**: Define our data model vocabulary
   - Create a JSON-LD context file
   - Map our attributes to standard vocabularies (Smart Data Models)

4. **Timestamps**: Use observedAt for temporal properties
   - Before: `"timestamp": 1710067980`
   - After: `"observedAt": "2024-05-03T07:15:00Z"`

### What Can Stay the Same

1. **Core Data Model**: Vehicle, Journey, Position entities remain
2. **GTFS Integration**: Can coexist with NGSI-LD
3. **Business Logic**: Backend processing unchanged
4. **Database Schema**: Can maintain current structure

## Implementation Strategy

### Phase 1: Research and Planning

1. Study Smart Data Models for transportation
   - Vehicle data models
   - Transit data models
   - Identify reusable vocabularies

2. Design @context file for Databus
   - Map our attributes to standard terms
   - Define custom terms where needed

3. Evaluate NGSI-LD Context Brokers
   - Orion-LD (lightweight)
   - Scorpio (federation support)
   - Stellio (with Keycloak)

### Phase 2: Dual API Support

Rather than replacing the current API, implement NGSI-LD as an additional interface:

1. Create NGSI-LD endpoints alongside existing REST API
   - `/ngsi-ld/v1/entities` for NGSI-LD operations
   - Keep `/api/*` for current REST API

2. Implement transformation layer
   - Convert between internal format and NGSI-LD
   - Maintain backward compatibility

3. Add NGSI-LD features incrementally
   - Start with basic CRUD operations
   - Add subscriptions
   - Implement temporal queries

### Phase 3: Integration and Testing

1. Deploy NGSI-LD Context Broker (probably Orion-LD)
2. Test with GTFS Realtime integration
3. Validate with FIWARE IoT Agents if needed
4. Document NGSI-LD endpoints

## Benefits of NGSI-LD Compatibility

1. **Interoperability**: Easier integration with other FIWARE-based systems
2. **Standardization**: Compliance with ETSI specifications
3. **Smart City Integration**: Can participate in FIWARE-based smart city platforms
4. **Data Federation**: Enable multi-agency data sharing
5. **Tool Ecosystem**: Access to FIWARE tools and components

## Challenges and Considerations

1. **Complexity**: NGSI-LD adds conceptual and implementation complexity
2. **Learning Curve**: Team needs to understand JSON-LD and Linked Data concepts
3. **Performance**: Additional transformation overhead
4. **Maintenance**: Need to maintain two API versions during transition
5. **Documentation**: Must document both APIs for different user groups

## Recommendations

Based on this investigation, I recommend a phased approach:

**Short Term (Next 3-6 months)**
- Create proof-of-concept NGSI-LD transformer for Vehicle entity
- Design @context file for core Databus entities
- Test with Orion-LD in development environment

**Medium Term (6-12 months)**
- Implement NGSI-LD endpoints for all entity types
- Add NGSI-LD support to documentation
- Create migration guide for API users

**Long Term (1-2 years)**
- Evaluate deprecating old REST API if NGSI-LD proves successful
- Integrate with FIWARE IoT Agents for sensor data
- Explore federation with other transit systems

## Technical Requirements

If we proceed with NGSI-LD implementation, we will need:

1. **Infrastructure**
   - NGSI-LD Context Broker (Orion-LD recommended)
   - Additional Docker containers
   - MongoDB backend for Orion-LD

2. **Development**
   - JSON-LD library for Python
   - NGSI-LD client library
   - Update API documentation tools

3. **Testing**
   - NGSI-LD test suite
   - Performance benchmarks
   - Compatibility tests

## References

1. NGSI-LD Specification v1.7.1: https://cim.etsi.org/NGSI-LD/official/front-page.html
2. FIWARE NGSI-LD Tutorials: https://ngsi-ld-tutorials.readthedocs.io/
3. Smart Data Models: https://smartdatamodels.org/
4. JSON-LD Specification: https://w3c.github.io/json-ld-syntax/
5. FIWARE Catalogue: https://www.fiware.org/catalogue

## Next Steps

1. Review this document with the development team
2. Decide on implementation timeline
3. Allocate resources for proof-of-concept
4. Begin designing the @context file
5. Set up test environment with Orion-LD
6. Create sample NGSI-LD entities for core data model

## Conclusion

NGSI-LD compatibility is technically feasible for the Databus project. The main question is whether the benefits of standardization and interoperability justify the additional complexity. For a transit system that may need to integrate with other urban mobility platforms or participate in smart city initiatives, NGSI-LD support would be valuable. However, it should be implemented carefully to avoid disrupting existing functionality and users.

The recommended approach is to implement NGSI-LD alongside the current API, allowing gradual adoption and learning while maintaining backward compatibility. This strategy minimizes risk while positioning the system for future integration opportunities.
