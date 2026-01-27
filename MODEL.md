# Functional Diagram

| Layer            | Services                            |
| ---------------- | ----------------------------------- |
| Ingestion        | `backend`, `mqtt-broker`            |
| State            | `state`                             |
| Persistence      | `store`                             |
| Event processing | `realtime-engine`, `message-broker` |
| Projection       | `publisher`, `scheduler`            |
| Learning         | `analytics`                         |

```mermaid
flowchart TD
    subgraph Ingestion
        direction TB
        api[API]
        mqtt[MQTT]
        mqtt-broker(("mqtt-broker<br/>(HiveMQ)"))
        backend(("backend<br/>(Django)"))
    end
    subgraph Processing
        realtime-engine(("realtime-engine<br/>(Python)"))
        message-broker(("message-broker<br/>(RabbitMQ)"))
    end
    subgraph State
        state(("state<br/>(Redis)"))
    end
    subgraph Persistence
        store(("store<br/>(PostgreSQL)"))
        gtfs-s[GTFS Schedule]
    end
    scheduler(("scheduler<br/>(Celery Beat)"))
    subgraph Projection
        direction LR
        publisher(("publisher<br/>(Celery)"))
        gtfs[GTFS Realtime]
    end
    subgraph Learning
        analytics(("analytics<br/>(Prefect)"))
    end

    api --> backend
    mqtt --> mqtt-broker
    backend --"commands"--> message-broker
    mqtt-broker --"forwards telemetry"--> realtime-engine
    realtime-engine --"updates"--> state
    message-broker --"forwards commands"--> realtime-engine
    realtime-engine --"observations"--> message-broker
    message-broker --"forwards observations"--> backend
    realtime-engine --"writes operational traces"--> store
    backend --"writes/reads"--> store
    store --"batch"--> analytics
    state --"snapshot"--> publisher
    scheduler --> publisher
    publisher --> gtfs
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
