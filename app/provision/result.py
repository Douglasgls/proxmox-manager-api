class ProvisionResult:
    def __init__(
        self,
        success: bool,
        started_at,
        finished_at,
        duration: float,
        steps: list,
        error: str | None = None,
    ):
        self.success = success
        self.started_at = started_at
        self.finished_at = finished_at
        self.duration = duration
        self.steps = steps
        self.error = error

    def __repr__(self):
        return f"ProvisionResult(success={self.success}, duration={self.duration}, steps={self.steps}, error={self.error})"
