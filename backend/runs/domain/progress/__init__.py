from importlib import import_module

from .states import RunProgressStates, choices
from .events import RunProgressEvents

__all__ = [
    "RunProgressStates",
    "choices",
    "RunProgressEvents",
    "RunProgressActions",
    "RunProgressGuards",
    "Transition",
    "TRANSITIONS",
]


def __getattr__(name: str):
    if name in {
        "RunProgressActions",
        "RunProgressGuards",
        "Transition",
        "TRANSITIONS",
    }:
        module_name = {
            "RunProgressActions": "actions",
            "RunProgressGuards": "guards",
            "Transition": "transitions",
            "TRANSITIONS": "transitions",
        }[name]
        module = import_module(f"{__name__}.{module_name}")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
