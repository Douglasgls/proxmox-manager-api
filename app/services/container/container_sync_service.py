import logging
from datetime import datetime
from time import perf_counter

from app.models.container import Container
from app.dto.response.container import ContainerStatusDTO
from app.integrations.proxmox import ProxmoxClient, ContainerStatus
from app.repositories.container_repository import ContainerRepository
from app.services.audit_log_service import AuditLogService

logger = logging.getLogger(__name__)


class ContainerSyncService:
    """Serviço responsável por sincronizar o estado runtime de containers entre Proxmox VE e DB local."""

    def __init__(
        self,
        repository: ContainerRepository,
        proxmox_client: ProxmoxClient,
        audit_log_service: AuditLogService | None = None,
    ):
        self.repository = repository
        self.proxmox_client = proxmox_client
        self.audit_log_service = audit_log_service

    def sync_container_runtime(
        self,
        container: Container,
        status_info: ContainerStatus | None = None,
    ) -> Container:
        logger.info("Synchronizing runtime state for container %s...", container.container_number)
        if status_info is None:
            status_info = self.proxmox_client.get_container_status(
                container.container_number
            )
        logger.info("Runtime status: %s", status_info.status)

        container.status = status_info.status
        if status_info.ip_address:
            container.ip_address = status_info.ip_address
        container.updated_at = datetime.now()

        updated_container = self.repository.update(container)
        logger.info("Runtime synchronized.")
        return updated_container

    def sync(self, container: Container) -> Container:
        started_at = perf_counter()
        updated_container = self.sync_container_runtime(container)

        self._log_action(
            action="sync",
            container=updated_container,
            started_at=started_at,
            success=True,
            message="Container sincronizado com Proxmox.",
        )
        return updated_container

    def sync_all(self) -> list[Container]:
        """Sincroniza o estado de runtime de todos os containers no banco com o Proxmox VE."""
        containers = self.repository.list()
        updated_containers = []
        for container in containers:
            try:
                updated = self.sync_container_runtime(container)
                updated_containers.append(updated)
            except Exception as e:
                logger.warning(
                    f"Falha ao sincronizar container {container.id} (vmid: {container.container_number}): {e}"
                )
        return updated_containers

    def get_status(self, container: Container) -> ContainerStatusDTO:
        proxmox_status = self.proxmox_client.get_container_status(
            container.container_number
        )
        self.sync_container_runtime(container, status_info=proxmox_status)

        return ContainerStatusDTO(
            container_id=container.id,
            container_number=container.container_number,
            status=proxmox_status.status,
            proxmox_status=proxmox_status.status,
            uptime_seconds=proxmox_status.uptime_seconds,
            cpu_usage_percent=proxmox_status.cpu_usage_percent,
            memory_usage_mb=proxmox_status.memory_usage_mb,
        )

    def _log_action(
        self,
        action: str,
        container: Container,
        started_at: float,
        success: bool,
        message: str,
    ):
        if not self.audit_log_service:
            return

        self.audit_log_service.log(
            entity="container",
            entity_id=container.id,
            action=action,
            details={
                "container_number": container.container_number,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "success": success,
                "message": message,
                "status": container.status,
            },
        )
