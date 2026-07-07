from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict


class JobResponseDTO(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: str
    type: str
    status: str
    progress: int
    target_container: str | None = None
    container_id: int | None = None
    current_step: str | None = None
    current_component: str | None = None
    output: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class JobCreatedResponseDTO(BaseModel):
    job_id: str
