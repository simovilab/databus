from importlib import import_module

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


def __getattr__(name: str):
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
    return sorted(set(globals()) | set(__all__))
