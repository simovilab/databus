from django.utils.timezone import now
from runs.services.registry import TransitionRegistry
from runs.models import Run


class RunLifecycleService:
    def __init__(self):
        self.registry = TransitionRegistry()

    def process_event(self, event, payload):
        run = self._load_run(payload)
        candidates = self.registry.find(run.run_status, event)
        for transition in candidates:
            if self._check_guards(run, transition, payload):
                return self._apply_transition(run, transition, payload)
        return None  # no transition

    def _load_run(self, payload):
        run_id = payload.get("run_id")
        return Run.objects.get(id=run_id)

    def _check_guards(self, run, transition, payload):
        return all(guard(run, payload) for guard in transition.guards)

    def _apply_transition(self, run, transition, payload):
        old_state = run.run_status
        run.run_status = transition.to_state
        run.last_event_at = now()
        run.save()
        self._emit_event(run, old_state, transition.to_state)
        return transition.to_state

    def _emit_event(self, run, old, new):
        pass
        # emit_event(
        #    "run_state_changed",
        #    {
        #        "run_id": run.id,
        #        "from": old,
        #        "to": new,
        #        "timestamp": run.last_event_at,
        #    },
        # )
