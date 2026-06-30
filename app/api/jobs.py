# from fastapi import APIRouter
# from fastapi import Depends

# from app.dto.request.create_job import (
#     CreateJobDTO
# )

# from app.core.dependencies import (
#     get_job_service
# )
# from app.services.job_service import JobService


# router = APIRouter()


# @router.post(
#     "/jobs"
# )
# def create(
#     dto: CreateJobDTO,
#     service: JobService = Depends(
#         get_job_service
#     )
# ):

#     return service.create(
#         dto.type,
#         dto.target
#     )