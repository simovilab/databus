"""Table-driven FSM for the run lifecycle: states, events, guards, actions, and transitions.

Submodules are lazy-loaded via module `__getattr__` below so importing this
package does not eagerly pull in the Redis/Django-touching `actions` and
`guards` modules unless a caller actually needs them.
"""

from importlib import import_module
from typing import Any

from .states import RunLifecycleStates, choices
from .events import RunLifecycleEvents

__all__ = [
    "RunLifecycleStates",
    "choices",
    "RunLifecycleEvents",
    "RunLifecycleActions",
    "RunLifecycleGuards",
    "Transition",
    "TRANSITIONS",
    "target_state_for_event",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve `RunLifecycleActions`/`RunLifecycleGuards`/`Transition`/`TRANSITIONS`/`target_state_for_event` from their owning submodule."""
    if name in {
        "RunLifecycleActions",
        "RunLifecycleGuards",
        "Transition",
        "TRANSITIONS",
        "target_state_for_event",
    }:
        module_name = {
            "RunLifecycleActions": "actions",
            "RunLifecycleGuards": "guards",
            "Transition": "transitions",
            "TRANSITIONS": "transitions",
            "target_state_for_event": "transitions",
        }[name]
        module = import_module(f"{__name__}.{module_name}")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Include the lazily-loaded names in `dir()` output for REPL/IDE discoverability."""
    return sorted(set(globals()) | set(__all__))
