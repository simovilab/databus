from operations.models import Run
from messages import publish_event
from realtime_engine.tasks import register_run, start_run, end_run
from feed.utils import validate_run_request_data


def process_submission(payload):
    publish_event("RUN_SUBMISSION_REQUESTED", payload)
    is_valid, error_code = validate_run_request_data(payload)
    if is_valid:
        publish_event("RUN_SUBMISSION_SUCCEEDED", payload)
        registration_result, run_id = register_run.delay(payload).get(timeout=15)
        if registration_result:
            publish_event("RUN_REGISTRATION_SUCCEEDED", payload)
            return {"run_id": run_id}, 200
        else:
            publish_event("RUN_REGISTRATION_FAILED", payload)
            return (
                {
                    "error": {
                        "code": "Run registration failed",
                        "message": "Failed to register run",
                    }
                },
                400,
            )
    else:
        publish_event("RUN_SUBMISSION_FAILED", payload)
        return (
            {
                "error": {
                    "code": "Run request validation failed",
                    "message": error_code,
                }
            },
            400,
        )


def process_confirmation(payload):
    start_run_result = start_run.delay(payload).get(timeout=15)
    if start_run_result:
        updated = Run.objects.filter(id=payload.get("run_id")).update(
            run_status="IN_PROGRESS"
        )
        if not updated:
            return {"error": "run_id no encontrado"}, 404
        publish_event("RUN_START_SUCCEEDED", payload)
        return {"run_status": "IN_PROGRESS"}, 200
    else:
        publish_event("RUN_CONFIRMATION_FAILED", payload)
        return {"error": "No funcionó :("}, 400


def process_completion(payload):
    end_run_result = end_run.delay(payload).get(timeout=15)
    if end_run_result:  # Si end run se cumple:
        publish_event("RUN_COMPLETION_SUCCEEDED", payload)
        return {"run_status": "COMPLETED"}, 200
    else:  # Si end run no se cumple:
        publish_event("RUN_COMPLETION_FAILED", payload)
        return {"error": "No se pudo completar el run"}, 400


def process_interruption(payload):
    publish_event("RUN_INTERRUPTED", payload)
    return {"run_status": "INTERRUPTED"}, 200
