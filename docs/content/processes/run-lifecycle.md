---
icon: lucide/file
---

# Run Lifecycle

This processes handles the main events in a run lifecycle, such as creation, completion, and failure. It follows the state machine defined in the [Run State Machine](../concepts/run-state-machine.md) documentation.

```mermaid
stateDiagram-v2
    [*] --> REQUESTED : 📣 run_requested
    REQUESTED --> VALIDATED : 📣 run_validated
    REQUESTED --> CANCELLED : 📣request_failed
    VALIDATED --> INITIALIZED : 📣 run_initialized
    VALIDATED --> CANCELLED : 📣 validation_failed
    INITIALIZED --> CONFIRMED : 📣 run_confirmed
    INITIALIZED --> CANCELLED : 📣 initialization_failed
    CONFIRMED --> TRACKING : 📣 run_tracking_started
    CONFIRMED --> CANCELLED : 📣 confirmation_failed
    TRACKING --> IN_PROGRESS : 📣 run_begun
    TRACKING --> CANCELLED : 📣 tracking_failed
    IN_PROGRESS --> COMPLETED : 📣 run_completed
    IN_PROGRESS --> INTERRUPTED : 📣 run_interrupted
    IN_PROGRESS --> NO_SIGNAL : 📣 lost_signal
    IN_PROGRESS --> SHORT_TURNED : 📣 run_short_turned
    NO_SIGNAL --> IN_PROGRESS : 📣 tracking_restored
    NO_SIGNAL --> [*] : 📣 tracking_expired
    COMPLETED --> [*]
    INTERRUPTED --> [*]
    CANCELLED --> [*]
    SHORT_TURNED --> [*]
```

What happens inside a request-response cycle has to be synchronous

- `POST api/create-run`
  - response: `run_lifecycle_state = INITIALIZED`
- `POST api/update-run`
  - request: `event: RUN_CONFIRMED`
    - response: `run_lifecycle_state = TRACKING`
  - request: `event: RUN_COMPLETED`
    - response: `run_lifecycle_state = COMPLETED`
  - request: `event: RUN_INTERRUPTED`
    - response: `run_lifecycle_state = INTERRUPTED`
  - request: `event: RUN_SHORT_TURNED`
    - response: `run_lifecycle_state = SHORT_TURNED`

REQUESTED
VALIDATED
INITIALIZED
CONFIRMED
TRACKING
IN_PROGRESS
NO_SIGNAL
COMPLETED
INTERRUPTED
CANCELLED
SHORT_TURNED
