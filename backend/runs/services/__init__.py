__all__ = ["RunLifecycleService", "RunProgressService"]


def __getattr__(name):
    if name == "RunLifecycleService":
        from .run_lifecycle import RunLifecycleService

        return RunLifecycleService
    if name == "RunProgressService":
        from .run_progress import RunProgressService

        return RunProgressService
    raise AttributeError(f"module 'runs' has no attribute {name!r}")
