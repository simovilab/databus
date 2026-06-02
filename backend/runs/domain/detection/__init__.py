"""Detection logic for the run state machines.

This package is the single home for the heuristics that turn raw vehicle
telemetry (and the periodic staleness scan) into state-machine events. Detectors
are pure functions of their inputs — they never touch Redis or the database — so
they are trivial to unit-test and cheap to change. All side effects (Redis set
mutations, DB writes) live in the FSM *actions*, executed by the services once an
event is fired.

Import submodules directly to keep this package's import side-effect-free:

    from runs.domain.detection.dispatch import detect_from_telemetry
    from runs.domain.detection.result import DetectionResult
"""
