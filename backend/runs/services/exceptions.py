from typing import Any


class RunLifecycleError(Exception):
    def __init__(self, errors: dict[str, Any]):
        self.errors = errors
