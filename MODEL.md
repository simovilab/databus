# Functional Diagram

```mermaid
flowchart TD
    API[API]
    MQTT[MQTT]
    subgraph Ingestion
        broker((broker))
        backend((backend))
    end
    subgraph State
        state((state))
    end
    subgraph Persistence
        store((store))
    end
    subgraph Projection
        publisher((publisher))
        planner((planner))
    end
    subgraph Learning
        analytics((analytics))
    end
    GTFS[GTFS Realtime]

    API --"backend"--> Ingestion
    MQTT --"broker"--> Ingestion
    Ingestion --"realtime-engine"--> State
    Ingestion --"backend"--> Persistence
    State <--"realtime-engine"--> Persistence
    State --"publisher"--> Projection
    Persistence --"analytics"--> Learning
    planner --> publisher
    Projection --> GTFS
```

GTFS-Realtime is a periodically published, contract-bound projection of a continuously evolving system state.

I'm observing a system (run) that evolves through a small number of meaningful states

```mermaid
stateDiagram-v2
    [*] --> IS_MOVING
    IS_MOVING --> IS_STOPPED
    IS_STOPPED --> IS_MOVING
    IS_MOVING --> IS_PAUSED
    IS_STOPPED --> IS_PAUSED
    IS_PAUSED --> IS_MOVING
    IS_PAUSED --> IS_STOPPED
    IS_MOVING --> [*]
    IS_STOPPED --> [*]
    IS_PAUSED --> [*]
```

FSMs shine because transitions encode semantics.

FSM execution produces a trace. A trace is a sequence of labeled transitions. Labels carry data.
