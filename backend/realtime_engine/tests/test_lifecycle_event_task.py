"""Unit tests for ``run_lifecycle_event``'s WARNING-vs-ERROR branching.

Detectors already gate on the run's current state before firing (see
``runs/domain/detection/tests/``), but a detection can still lose a race
against an in-flight transition for the same run — two detections both read
the pre-transition state before the first one's ``run_lifecycle_event`` task
lands. When the *second* one is then processed, the run has already reached
its target state and ``RunLifecycleService.process_event`` rejects it as
"no valid transition". That rejection is a harmless no-op, not a bug, so it
must log at WARNING with a concise message — not ERROR with a traceback.
A rejection where the run is nowhere near the event's target state is a
genuine invalid transition and must stay loud.

``RunLifecycleService.process_event`` is mocked; only the task's own
exception handling is under test here.
"""

import logging
from unittest.mock import patch

import realtime_engine.tasks as tasks_module
from runs.services.exceptions import RunLifecycleError

RUN_ID = "run-flood-1"
LOGGER_NAME = "realtime_engine.tasks"


def _rejection(current_state: str) -> RunLifecycleError:
    return RunLifecycleError(
        {
            "detail": "No valid transition for event 'run_started' from state "
            f"'{current_state}'.",
            "attempts": [],
            "current_state": current_state,
        }
    )


def test_idempotent_refire_logs_warning_not_error(caplog):
    """run_started rejected because the run is already IN_PROGRESS (its own
    target state) is a race-condition no-op."""
    with patch.object(
        tasks_module.RunLifecycleService,
        "process_event",
        side_effect=_rejection("In Progress"),
    ):
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            tasks_module.run_lifecycle_event("run_started", {"run_id": RUN_ID})

    levels = [r.levelno for r in caplog.records]
    assert logging.WARNING in levels
    assert logging.ERROR not in levels and logging.CRITICAL not in levels


def test_genuine_invalid_transition_still_logs_error(caplog):
    """run_started rejected while the run is somewhere run_started could
    never have led it (still CONFIRMED, never TRACKING) is a real bug."""
    with patch.object(
        tasks_module.RunLifecycleService,
        "process_event",
        side_effect=_rejection("Confirmed"),
    ):
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            tasks_module.run_lifecycle_event("run_started", {"run_id": RUN_ID})

    levels = [r.levelno for r in caplog.records]
    assert logging.ERROR in levels


def test_unrelated_exception_still_logs_error(caplog):
    """Non-lifecycle failures (e.g. the run row vanished) are unaffected by
    the idempotent-refire carve-out."""
    with patch.object(
        tasks_module.RunLifecycleService,
        "process_event",
        side_effect=RuntimeError("boom"),
    ):
        with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
            tasks_module.run_lifecycle_event("run_started", {"run_id": RUN_ID})

    levels = [r.levelno for r in caplog.records]
    assert logging.ERROR in levels
