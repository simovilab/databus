from celery import shared_task
from messages.publish import databus_event
from typing import Any


@shared_task(queue="realtime_engine")
def hello_world() -> None:
    print("Hello, world!")


@shared_task(queue="realtime_engine")
def validate_run(run_data: dict[str, Any]) -> bool:
    # Aquí iría la lógica de validación del run_data
    return True


@shared_task(queue="realtime_engine")
def initialize_run(run_data: dict[str, Any]) -> bool:
    # Aquí iría la lógica de inicialización del run_data
    return True


@shared_task(queue="realtime_engine")
def register_run(run_data: dict[str, Any]) -> tuple[bool, str | None]:
    validation_result = validate_run(run_data)
    if validation_result:
        databus_event("RUN_VALIDATION_SUCCEEDED", run_data)
        intialization_result = initialize_run(run_data)
        if intialization_result:
            databus_event("RUN_INITIALIZATION_SUCCEEDED", run_data)
            return (True, "94268469")
        else:
            databus_event("RUN_INITIALIZATION_FAILED", run_data)
            return (False, None)
    else:
        databus_event("RUN_VALIDATION_FAILED", run_data)
        return (False, None)


@shared_task(queue="realtime_engine")
def start_run(run_data: dict[str, Any]) -> bool:
    # Aquí iría la lógica de inicio del run_data
    return True


@shared_task(queue="realtime_engine")
def end_run(run_data: dict[str, Any]) -> bool:
    # Aquí iría la lógica de finalización del run_data
    return True
