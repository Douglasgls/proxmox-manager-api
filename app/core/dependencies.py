from fastapi import Depends
from functools import lru_cache

from app.database.session import SessionLocal


from app.repositories.user_repository import (
    UserRepository
)

from app.repositories.container_repository import (
    ContainerRepository
)

from app.repositories.job_repository import (
    JobRepository
)

from app.repositories.container_action_repository import (
    ContainerActionRepository
)

from app.repositories.audit_log_repository import (
    AuditLogRepository
)

from app.integrations.proxmox import (
    ProxmoxClient
)
from app.provision.engine import ProvisionEngine


from app.services.user_service import (
    UserService
)

from app.services.container_service import (
    ContainerService
)

from app.services.container_creation_workflow import (
    ContainerCreationWorkflow
)

from app.services.job_service import (
    JobService
)

from app.services.template_service import (
    TemplateService
)

# from app.services.container_action_service import (
#     ContainerActionService
# )

from app.services.audit_log_service import (
    AuditLogService
)
from app.core.settings import Settings
from app.security.jwt import JWTManager
from app.security.password import PasswordManager
from app.services.auth_service import AuthService
from app.services.monitoring.collectors.inventory.container_inventory_collector import (
    ContainerInventoryCollector,
)
from app.services.monitoring.collectors.inventory.host_inventory_collector import (
    HostInventoryCollector,
)
from app.services.monitoring.collectors.inventory.network_inventory_collector import (
    NetworkInventoryCollector,
)
from app.services.monitoring.collectors.inventory.storage_inventory_collector import (
    StorageInventoryCollector,
)
from app.services.monitoring.collectors.metrics.container_metrics_collector import (
    ContainerMetricsCollector,
)
from app.services.monitoring.collectors.metrics.host_metrics_collector import (
    HostMetricsCollector,
)
from app.services.monitoring.container_monitoring_service import (
    ContainerMonitoringService,
)
from app.services.monitoring.host_monitoring_service import (
    HostMonitoringService,
)
from app.services.monitoring.network_monitoring_service import (
    NetworkMonitoringService,
)
from app.services.monitoring.storage_monitoring_service import (
    StorageMonitoringService,
)
from app.tailscale.manager import TailscaleManager
from app.tailscale.service import TailscaleService
from app.tailscale.repository import TailscaleRepository
from app.integrations.proxmox.container_session import ContainerSession



def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


def get_proxmox_client():

    return ProxmoxClient()


@lru_cache
def get_settings() -> Settings:
    return Settings.from_environment()


@lru_cache
def get_password_manager() -> PasswordManager:
    return PasswordManager()


def get_jwt_manager(
    settings: Settings = Depends(get_settings),
) -> JWTManager:
    return JWTManager(settings)


def get_auth_service(
    db=Depends(get_db),
    password_manager: PasswordManager = Depends(get_password_manager),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
):
    return AuthService(
        user_service=UserService(UserRepository(db)),
        password_manager=password_manager,
        jwt_manager=jwt_manager,
    )


def get_host_monitoring_service(
    proxmox_client: ProxmoxClient = Depends(get_proxmox_client),
):
    return HostMonitoringService(
        inventory_collector=HostInventoryCollector(proxmox_client),
        metrics_collector=HostMetricsCollector(proxmox_client),
    )


def get_container_monitoring_service(
    proxmox_client: ProxmoxClient = Depends(get_proxmox_client),
):
    return ContainerMonitoringService(
        inventory_collector=ContainerInventoryCollector(proxmox_client),
        metrics_collector=ContainerMetricsCollector(proxmox_client),
    )


def get_storage_monitoring_service(
    proxmox_client: ProxmoxClient = Depends(get_proxmox_client),
):
    return StorageMonitoringService(
        inventory_collector=StorageInventoryCollector(proxmox_client),
    )


def get_network_monitoring_service(
    proxmox_client: ProxmoxClient = Depends(get_proxmox_client),
):
    return NetworkMonitoringService(
        inventory_collector=NetworkInventoryCollector(proxmox_client),
    )


def get_provision_engine():

    return ProvisionEngine()


def get_user_service(db=Depends(get_db)):

    return UserService(
        UserRepository(db)
    )


def get_container_service(
    db=Depends(get_db),
    provision_engine=Depends(get_provision_engine),
):

    return ContainerService(
        repository=ContainerRepository(db),
        proxmox_client=ProxmoxClient(),
        audit_log_service=AuditLogService(
            AuditLogRepository(db)
        ),
        provision_engine=provision_engine,
    )


def get_job_service(db=Depends(get_db)):

    return JobService(
        JobRepository(db)
    )


def get_container_creation_workflow(
    container_service=Depends(get_container_service),
    job_service=Depends(get_job_service),
):

    return ContainerCreationWorkflow(
        container_service=container_service,
        job_service=job_service,
    )


def get_template_service(db=Depends(get_db)):

    return TemplateService(
        ProxmoxClient(),
        JobService(
            JobRepository(db)
        )
    )


# def get_container_action_service(
#     db=Depends(get_db)
# ):

#     return ContainerActionService(
#         ContainerActionRepository(
#             db
#         )
#     )


def get_audit_service(
    db=Depends(get_db)
):

    return AuditLogService(
        AuditLogRepository(db)
    )


def get_tailscale_manager(
    db=Depends(get_db),
    job_service: JobService = Depends(get_job_service),
    proxmox_client: ProxmoxClient = Depends(get_proxmox_client),
):
    repository = TailscaleRepository(db)
    
    # Factory to create the manager per container ID request
    def factory(container_id: str, proxmox_container_id: int):
        container_session = ContainerSession(proxmox_client, proxmox_container_id)
        tailscale_service = TailscaleService(container_session)
        return TailscaleManager(
            job_service=job_service,
            container_session=container_session,
            tailscale_service=tailscale_service,
            repository=repository,
        )
    return factory
