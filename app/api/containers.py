from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import status

from app.dto.request.create_container import (
    CreateContainerDTO
)
from app.dto.request.container_network import (
    UpdateContainerNetworkDTO
)

from app.dto.response.container import (
    ContainerOperationDTO,
    ContainerResponseDTO,
    NetworkBridgeDTO,
    ContainerStatusDTO,
)

from app.core.dependencies import (
    get_container_service,
    get_container_creation_workflow,
)
from app.dto.response.job import JobCreatedResponseDTO
from app.services.container_creation_workflow import ContainerCreationWorkflow
from app.services.container_service import ContainerService


router = APIRouter()


@router.post(
    "/containers",
    response_model=JobCreatedResponseDTO,
    status_code=status.HTTP_202_ACCEPTED,
)
def create(
    dto: CreateContainerDTO,
    background_tasks: BackgroundTasks,
    workflow: ContainerCreationWorkflow = Depends(
        get_container_creation_workflow
    ),
):

    job = workflow.create_job()

    background_tasks.add_task(
        workflow.run,
        job.id,
        dto,
    )

    return JobCreatedResponseDTO(
        job_id=job.id
    )

@router.get(
    "/containers",
    response_model=list[ContainerResponseDTO],
)
def list_all(
    service: ContainerService = Depends(
        get_container_service
    )
):

    return service.list()


@router.get(
    "/proxmox/networks",
    response_model=list[NetworkBridgeDTO],
)
def list_networks(
    service: ContainerService = Depends(
        get_container_service
    )
):

    return service.list_networks()


@router.get(
    "/containers/{id}",
    response_model=ContainerResponseDTO,
)
def get(
    id: str,
    service: ContainerService = Depends(
        get_container_service
    )
):

    return service.get(
        id
    )


@router.post(
    "/containers/{id}/start",
    response_model=ContainerOperationDTO,
)
def start(
    id: str,
    service: ContainerService = Depends(
        get_container_service
    )
):

    return service.start(
        id
    )


@router.post(
    "/containers/{id}/stop",
    response_model=ContainerOperationDTO,
)
def stop(
    id: str,
    service: ContainerService = Depends(
        get_container_service
    )
):

    return service.stop(
        id
    )


@router.post(
    "/containers/{id}/restart",
    response_model=ContainerOperationDTO,
)
def restart(
    id: str,
    service: ContainerService = Depends(
        get_container_service
    )
):

    return service.restart(
        id
    )


@router.delete(
    "/containers/{id}",
    response_model=ContainerOperationDTO,
)
def delete(
    id: str,
    service: ContainerService = Depends(
        get_container_service
    )
):

    return service.delete(
        id
    )


@router.get(
    "/containers/{id}/status",
    response_model=ContainerStatusDTO,
)
def get_status(
    id: str,
    service: ContainerService = Depends(
        get_container_service
    )
):

    return service.get_status(
        id
    )


@router.post(
    "/containers/{id}/sync",
    response_model=ContainerResponseDTO,
)
def sync(
    id: str,
    service: ContainerService = Depends(
        get_container_service
    )
):

    return service.sync(
        id
    )


@router.patch(
    "/containers/{id}/network",
    response_model=ContainerResponseDTO,
)
def update_network(
    id: str,
    dto: UpdateContainerNetworkDTO,
    service: ContainerService = Depends(
        get_container_service
    )
):

    return service.update_network(
        id,
        **dto.model_dump(
            exclude_unset=True
        )
    )
