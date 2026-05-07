from runs.models import Run


class RunProgressService:
    def process_event(self, event, payload):
        run = self._load_run(payload)
        if not self._is_active(run):
            return None
        context = self._build_context(run, payload)
        detected_events = self._detect_events(run, event, payload, context)
        return self._persist_events(run, detected_events)

    def _load_run(self, payload):
        run_id = payload.get("run_id")
        return Run.objects.get(id=run_id)

    def _is_active(self, run):
        return run.run_lifecycle_state == "IN_PROGRESS"

    def _build_context(self, run, payload):
        context = {
            "timestamp": payload.get("timestamp"),
            "position": payload.get("position"),
            "speed": payload.get("speed"),
            # TODO:
            # - last known position (Redis)
            # - stop sequence (GTFS)
            # - shape
        }
        return context

    def _detect_events(self, run, event, payload, context):
        detected = []
        if event == "vehicle_position_updated":
            detected.extend(self._detect_stop_events(run, context))
            detected.extend(self._detect_movement_events(run, context))
        return detected

    def _detect_stop_events(self, run, context):
        events = []
        current_stop = 1  # self._infer_current_stop(run, context)
        if current_stop and not self._was_at_stop(run, current_stop):
            events.append(
                {
                    "type": "vehicle_arrived_at_stop",
                    "stop_id": current_stop,
                    "timestamp": context["timestamp"],
                }
            )
        return events

    def _detect_movement_events(self, run, context):
        events = []
        if context["speed"] > 5:
            events.append(
                {
                    "type": "vehicle_moving",
                    "timestamp": context["timestamp"],
                }
            )
        return events
