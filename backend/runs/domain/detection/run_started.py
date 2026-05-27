from runs.domain.lifecycle import RunLifecycleStates


class RunStartedDetector:
    fsm = "progression"

    @staticmethod
    def detect(run_state: str, leaf: str, data: dict, payload: dict):
        if run_state == RunLifecycleStates.TRACKING.value and leaf == "position":
            speed = float(data.get("speed", 0))
            if speed > 0.5:
                return True
        return False
