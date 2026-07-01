from fastapi import APIRouter
from fastapi import Depends

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

    # TODO: validar os dados e lembrar de apenas desestruturar o DTO
    return service.create(
        name=dto.name,
        cpu=dto.cpu,
        memory_mb=dto.memory_mb,
        disk_gb=dto.disk_gb,
        image_name=dto.image_name,
        password=dto.password,
        bridge=dto.bridge,
        ip_mode=dto.ip_mode,
        ip_address=dto.ip_address,
        cidr=dto.cidr,
        gateway=dto.gateway,
        firewall=dto.firewall,
        mtu=dto.mtu,
        vlan=dto.vlan,
        mac_address=dto.mac_address,
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
