from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import Depends

from app.core.dependencies import (
    get_template_service,
)
from app.dto.request.template import (
    DownloadTemplateDTO,
)
from app.dto.response.job import (
    JobResponseDTO,
)
from app.dto.response.template import (
    OsTemplateResponseDTO,
)
from app.services.template_service import (
    TemplateService,
    run_template_download_job,
)


router = APIRouter()


@router.get(
    "/proxmox/templates/available",
    response_model=list[OsTemplateResponseDTO],
)
def list_available_templates(
    service: TemplateService = Depends(
        get_template_service
    ),
):

    return service.list_available_templates()


@router.get(
    "/proxmox/templates/installed",
    response_model=list[OsTemplateResponseDTO],
)
def list_installed_templates(
    service: TemplateService = Depends(
        get_template_service
    ),
):

    return service.list_installed_templates()


@router.post(
    "/proxmox/templates/download",
    response_model=JobResponseDTO,
)
def download_template(
    dto: DownloadTemplateDTO,
    background_tasks: BackgroundTasks,
    service: TemplateService = Depends(
        get_template_service
    ),
):

    job = service.create_download_job(
        storage=dto.storage,
        template=dto.template,
    )
    background_tasks.add_task(
        run_template_download_job,
        job.id,
        dto.storage,
        dto.template,
    )

    return job


@router.delete(
    "/proxmox/templates/{template:path}",
    response_model=OsTemplateResponseDTO,
)
def delete_template(
    template: str,
    service: TemplateService = Depends(
        get_template_service
    ),
):

    return service.delete_template(
        template
    )
