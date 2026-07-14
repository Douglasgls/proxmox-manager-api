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
from app.security.dependencies import get_current_user


router = APIRouter()


@router.get(
    "/jobs",
    response_model=list[JobResponseDTO],
    dependencies=[Depends(get_current_user)],
)
def list_all(
    service: JobService = Depends(
        get_job_service
    ),
):

    return service.list()


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponseDTO,
    dependencies=[Depends(get_current_user)],
)
def get(
    job_id: str,
    service: JobService = Depends(
        get_job_service
    ),
):

    return service.get(
        job_id
    )



