from fastapi import APIRouter
from fastapi import Depends

from app.core.dependencies import (
    get_job_service,
)
from app.dto.response.job import (
    JobResponseDTO,
)
from app.services.job_service import (
    JobService,
)


router = APIRouter()


@router.get(
    "/jobs",
    response_model=list[JobResponseDTO],
)
def list_all(
    service: JobService = Depends(
        get_job_service
    ),
):

    return service.list()


@router.get(
    "/jobs/{id}",
    response_model=JobResponseDTO,
)
def get(
    id: str,
    service: JobService = Depends(
        get_job_service
    ),
):

    return service.get(
        id
    )
