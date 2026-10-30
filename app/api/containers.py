from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.dto.request.create_container import (
    CreateContainerDTO,
    InstallContainerComponentsDTO,
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
    get_db,
    get_container_service,
    get_container_creation_workflow,
    get_job_service,
    get_tailscale_manager,
    get_access_token_manager,
    get_component_service,
    get_container_component_install_workflow,
    get_container_component_service,
)
from app.dto.response.job import JobCreatedResponseDTO
from app.services.container_creation_workflow import ContainerCreationWorkflow
from app.services.container_component_install_workflow import ContainerComponentInstallWorkflow
from app.services.container_service import ContainerService
from app.services.component_service import ComponentService
from app.services.container_component_service import ContainerComponentService
from app.core.exceptions import DomainValidationError
from app.security.dependencies import get_current_user
from app.models.user import User

from app.access.manager import AccessTokenManager
from app.access.dto import (
    AccessTokenCreateResponseDTO,
    AccessTokenCreateRequestDTO,
    AccessTokenMetadataDTO,
    ClientConnectionDTO,
)
from sqlalchemy.orm import Session


router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post(
    "/containers",
    response_model=JobCreatedResponseDTO,
    status_code=status.HTTP_202_ACCEPTED,
)
def create(
    dto: CreateContainerDTO,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    workflow: ContainerCreationWorkflow = Depends(
        get_container_creation_workflow
    ),
    component_service: ComponentService = Depends(
        get_component_service
    ),
):

    if dto.components:
        component_service.validate_and_resolve_slugs(dto.components)

    job = workflow.create_job()

    background_tasks.add_task(
        workflow.run,
        job.id,
        dto,
        current_user.id,
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

@router.post(
    "/containers/{id}/tailscale/setup",
    response_model=JobCreatedResponseDTO,
    status_code=status.HTTP_202_ACCEPTED,
)
def tailscale_setup(
    id: str,
    background_tasks: BackgroundTasks,
    container_service: ContainerService = Depends(get_container_service),
    job_service = Depends(get_job_service),
    tailscale_manager_factory = Depends(get_tailscale_manager),
):
    from app.database.session import SessionLocal
    from app.cloud.repository import AgentSettingsRepository
    from app.cloud.manager import cloud_manager

    with SessionLocal() as db:
        settings = AgentSettingsRepository(db).get()
        if not settings or not settings.environment_token_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A Cloud Control Plane não está vinculada. Vincule o Agent à Cloud para permitir acesso remoto.",
            )

    if not (cloud_manager.connection_manager and cloud_manager.connection_manager._ws_client and cloud_manager.connection_manager._ws_client.is_connected):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A Cloud Control Plane está desconectada. Restabeleça a conexão para permitir acesso remoto.",
        )

    # Verify container exists
    container = container_service.get(id)
    
    # Create the job
    job = job_service.create(
        job_type="tailscale_setup",
        target=container.id
    )
    
    manager = tailscale_manager_factory(container.id, container.container_number)
    
    background_tasks.add_task(
        manager.setup,
        job.id,
        container.id,
        container.container_number
    )
    
    return JobCreatedResponseDTO(
        job_id=job.id
    )


@router.post(
    "/containers/{id}/access-token",
    response_model=AccessTokenCreateResponseDTO,
)
def create_access_token(
    id: str,
    dto: AccessTokenCreateRequestDTO | None = None,
    manager: AccessTokenManager = Depends(get_access_token_manager),
    container_service: ContainerService = Depends(get_container_service),
):
    try:
        container_service.get(id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container '{id}' não encontrado",
        )

    from app.database.session import SessionLocal
    from app.cloud.repository import AgentSettingsRepository
    from app.cloud.manager import cloud_manager

    with SessionLocal() as db:
        settings = AgentSettingsRepository(db).get()
        if not settings or not settings.environment_token_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A Cloud Control Plane não está vinculada. Vincule o Agent à Cloud para gerar tokens de acesso.",
            )

    if not (cloud_manager.connection_manager and cloud_manager.connection_manager._ws_client and cloud_manager.connection_manager._ws_client.is_connected):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A Cloud Control Plane está desconectada. Restabeleça a conexão para gerar tokens de acesso.",
        )

    expires_in_days = dto.expires_in_days if dto else None
    expires_in_hours = dto.expires_in_hours if dto else None
    expires_in_minutes = dto.expires_in_minutes if dto else None
    description = dto.description if dto else None
    return manager.create_token(
        container_id=id,
        description=description,
        expires_in_days=expires_in_days,
        expires_in_hours=expires_in_hours,
        expires_in_minutes=expires_in_minutes,
    )


@router.get(
    "/containers/{id}/access-token",
    response_model=list[AccessTokenMetadataDTO],
)
def get_access_tokens(
    id: str,
    manager: AccessTokenManager = Depends(get_access_token_manager),
    container_service: ContainerService = Depends(get_container_service),
):
    try:
        container_service.get(id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container '{id}' não encontrado",
        )

    return manager.list_tokens_metadata(id)


@router.get(
    "/containers/{id}/connections",
    response_model=list[ClientConnectionDTO],
)
def get_container_connections(
    id: str,
    db: Session = Depends(get_db),
    container_service: ContainerService = Depends(get_container_service),
):
    try:
        container_service.get(id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container '{id}' não encontrado",
        )

    from app.models.client_connection import ClientConnection
    from sqlalchemy import or_

    connections = (
        db.query(ClientConnection)
        .filter(or_(ClientConnection.container_id == id, ClientConnection.container_id.is_(None)))
        .order_by(ClientConnection.online.desc(), ClientConnection.last_seen.desc())
        .all()
    )

    from app.access.manager import _ensure_utc
    return [
        ClientConnectionDTO(
            id=c.id,
            hostname=c.hostname,
            tailscale_ip=c.tailscale_ip,
            online=c.online,
            status=c.status,
            last_seen=_ensure_utc(c.last_seen),
            created_at=_ensure_utc(c.created_at),
        )
        for c in connections
    ]


@router.post(
    "/containers/{id}/components",
    response_model=JobCreatedResponseDTO,
    status_code=status.HTTP_202_ACCEPTED,
)
def install_components(
    id: str,
    dto: InstallContainerComponentsDTO,
    background_tasks: BackgroundTasks,
    service: ContainerService = Depends(get_container_service),
    component_service: ComponentService = Depends(get_component_service),
    workflow: ContainerComponentInstallWorkflow = Depends(get_container_component_install_workflow),
    container_component_service: ContainerComponentService = Depends(get_container_component_service),
):
    container = service.get(id)

    if not dto.components:
        raise DomainValidationError("A lista de componentes não pode estar vazia.")

    existing_records = container_component_service.repository.list_by_container(container.id)
    component_service.validate_and_resolve_slugs(
        dto.components,
        existing_container_components=existing_records,
    )

    job_dto = workflow.create_job(container_id=id)

    background_tasks.add_task(
        workflow.run,
        job_dto.job_id,
        id,
        dto,
    )

    return job_dto
