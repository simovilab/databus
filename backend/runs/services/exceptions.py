class RunLifecycleError(Exception):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
