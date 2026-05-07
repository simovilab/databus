from typing import Any
from runs.models import Run


class RunLifecycleActions:
    @staticmethod
    def update_run_lifecycle_state(run: Run, payload: dict[str, Any]) -> bool:
        new_state = payload.get("new_state")
        run.run_lifecycle_state = new_state
        run.save()
        return True

    @staticmethod
    def update_system_state(run: Run, payload: dict[str, Any]) -> bool:
        run = run
        payload = payload
        return True
