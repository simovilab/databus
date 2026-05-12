---
icon: lucide/file
---

# Run Lifecycle

This processes handles the main events in a run lifecycle, such as creation, completion, and failure. It follows the state machine defined in the [Run State Machine](../concepts/run-state-machine.md) documentation.

```mermaid
stateDiagram-v2
    [*] --> REQUESTED : run_requested
    REQUESTED --> VALIDATED : validate_run
    REQUESTED --> CANCELLED : run_rejected
    VALIDATED --> INITIALIZED : initialize_run
    VALIDATED --> CANCELLED : run_rejected
    INITIALIZED --> CONFIRMED : run_confirmed_by_operator
    INITIALIZED --> CANCELLED : run_rejected
    CONFIRMED --> TRACKING : run_tracking_started
    CONFIRMED --> CANCELLED : cancel_run
    TRACKING --> IN_PROGRESS : run_started
    TRACKING --> CANCELLED : cancel_run
    IN_PROGRESS --> COMPLETED : complete_run
    IN_PROGRESS --> INTERRUPTED : interrupt_run
    IN_PROGRESS --> SHORT_TURNED : short_turn_run
    IN_PROGRESS --> NO_SIGNAL : run_tracking_lost
    NO_SIGNAL --> IN_PROGRESS : run_tracking_restored
    NO_SIGNAL --> CANCELLED : run_tracking_expired
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
