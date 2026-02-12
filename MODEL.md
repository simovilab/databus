# Functional Diagram

| Layer            | Services                            |
| ---------------- | ----------------------------------- |
| Ingestion        | `backend`, `telemetry-broker`       |
| State            | `state`                             |
| Persistence      | `store`                             |
| Event processing | `realtime-engine`, `message-broker` |
| Projection       | `publisher`, `scheduler`            |
| Learning         | `analytics-engine`                  |

```mermaid
flowchart TD
    subgraph Ingestion
        api([REST API])
        mqtt([MQTT])
    end
    telemetry-broker(("telemetry-broker<br/>(HiveMQ)"))
    backend(("backend<br/>(Django)"))
    subgraph Processing
        realtime-engine(("realtime-engine<br/>(Python)"))
    end
    message-broker(("message-broker<br/>(RabbitMQ)"))
    subgraph State
        state(("state<br/>(Redis)"))
    end
    subgraph Persistence
        store(("store<br/>(PostgreSQL)"))
        gtfs-s[/GTFS Schedule/]
    end
    scheduler(("scheduler<br/>(Celery Beat)"))
    subgraph Projection
        publisher(("publisher<br/>(Celery)"))
        gtfs-rt[/GTFS Realtime/]
    end
    subgraph Learning
        analytics-engine(("analytics-engine<br/>(Prefect)"))
    end

    api --> backend
    mqtt --> telemetry-broker
    backend <--"writes / reads"--> store
    telemetry-broker --"forwards telemetry"--> realtime-engine
    backend --"emits commands"--> message-broker
    realtime-engine --"emits observations"--> message-broker
    realtime-engine --"writes traces"--> store
    realtime-engine --"updates"--> state
    scheduler --> publisher
    state --"provides snapshot"--> publisher
    publisher --"publishes"--> gtfs-rt
    publisher --"writes records"--> store
    publisher --"emits assertions"--> message-broker
    message-broker --"forwards commands"--> realtime-engine
    message-broker --"forwards observations"--> backend
    message-broker --"forwards assertions"--> backend
    message-broker --"forwards commands"--> publisher
    gtfs-s -->  store
    store --"processes batches"--> analytics-engine

```

## A Day in the Life of a Run

```mermaid
sequenceDiagram
    actor Dispatcher
    participant Backend
    participant Store
    participant Message Broker
    participant Realtime Engine
    participant State
    participant Vehicle
    participant MQTT Broker
    participant Publisher

    Dispatcher->>Backend: Begin run
    Backend->>Store: Query run metadata
    Store->>Backend: Return run metadata
    Backend->>Message Broker: Request to begin run
    Message Broker->>Realtime Engine: Forward request
    Realtime Engine->>State: Populate run metadata
    loop Every 15 seconds
        loop Every few seconds
            Vehicle->>MQTT Broker: Send telemetry
            MQTT Broker->>Realtime Engine: Forward telemetry
            Realtime Engine->>State: Update state
            opt Observation
                Realtime Engine->>Message Broker: Emit observation
                Message Broker->>Backend: Forward observation
            end
        end
        State->>Publisher: Provide snapshot
        Note right of Publisher: Publish GTFS Realtime
        Publisher->>Store: Write record
        opt Assertion
            Publisher->>Message Broker: Emit assertion
            Message Broker->>Backend: Forward assertion
        end
    end
    Dispatcher->>Backend: End run
    Backend->>Message Broker: Request to end run
    Message Broker->>Realtime Engine: Forward request
    Realtime Engine->>State: Flush run metadata
    Realtime Engine->>Store: Write trace data
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
