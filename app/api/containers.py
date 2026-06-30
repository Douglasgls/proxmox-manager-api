from fastapi import APIRouter
from fastapi import Depends

from app.dto.request.create_container import (
    CreateContainerDTO
)

from app.dto.response.container import (
    ContainerOperationDTO,
    ContainerResponseDTO,
    ContainerStatusDTO,
)

from app.core.dependencies import (
    get_container_service
)
from app.services.container_service import ContainerService


router = APIRouter()


@router.post(
    "/containers",
    response_model=ContainerResponseDTO,
)
def create(
    dto: CreateContainerDTO,
    service: ContainerService = Depends(
        get_container_service
    )
):

    return service.create(
        name=dto.name,
        cpu=dto.cpu,
        memory_mb=dto.memory_mb,
        disk_gb=dto.disk_gb,
        image_name=dto.image_name,
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
