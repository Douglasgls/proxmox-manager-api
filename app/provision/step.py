class ProvisionStep:
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_ERROR = "error"

    def __init__(
        self,
        component_name: str,
        status: str = STATUS_PENDING,
        started_at=None,
        finished_at=None,
        message: str | None = None,
    ):
        self.component_name = component_name
        self.status = status
        self.started_at = started_at
        self.finished_at = finished_at
        self.message = message

    def start(
        self,
        started_at,
        message: str | None = None,
    ):
        self.status = self.STATUS_RUNNING
        self.started_at = started_at
        self.message = message

    def finish(
        self,
        finished_at,
        message: str | None = None,
    ):
        self.status = self.STATUS_SUCCESS
        self.finished_at = finished_at
        self.message = message

    def fail(
        self,
        finished_at,
        message: str,
    ):
        self.status = self.STATUS_ERROR
        self.finished_at = finished_at
        self.message = message

    def __repr__(self):
        return f"ProvisionStep(component_name={self.component_name}, status={self.status}, started_at={self.started_at}, finished_at={self.finished_at}, message={self.message})"
