from typing import Protocol, runtime_checkable


@runtime_checkable
class TelemetrySource(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
