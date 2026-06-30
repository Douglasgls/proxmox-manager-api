from datetime import datetime
from time import perf_counter

from app.models.container import (
    Container
)

from app.dto.response.container import (
    ContainerOperationDTO,
    ContainerStatusDTO,
)

from app.integrations.proxmox import (
    ContainerInfo,
    ProxmoxClient,
)

from app.repositories.container_repository import (
    ContainerRepository
)
from app.services.audit_log_service import (
    AuditLogService
)


class ContainerService:

    def __init__(
        self,
        repository: ContainerRepository,
        proxmox_client: ProxmoxClient,
        audit_log_service: AuditLogService | None = None
    ):
        self.repository = repository
        self.proxmox_client = proxmox_client
        self.audit_log_service = audit_log_service


    def create(
        self,
        name,
        cpu,
        memory_mb,
        disk_gb=2,
        image_name=None
    ):

        started_at = perf_counter()
        existing = (
            self.repository
            .get_by_name(
                name
            )
        )

        if existing:
            raise ValueError(
                "Container já existe"
            )

        proxmox_container = (
            self.proxmox_client
            .create_container(
                name=name,
                cpu=cpu,
                memory_mb=memory_mb,
                disk_gb=disk_gb,
                image_name=image_name,
            )
        )

        container = Container(
            container_number=proxmox_container.container_id,
            name=name,
            cpu=cpu,
            memory_mb=memory_mb,
            status=proxmox_container.status,
            disk_gb=(
                proxmox_container.disk_gb
                or 2
            ),
            ip_address=proxmox_container.ip_address,
            image_name=proxmox_container.image_name,
        )

        created_container = (
            self.repository
            .create(
                container
            )
        )

        self._log_action(
            action="create",
            container=created_container,
            started_at=started_at,
            success=True,
            message="Container criado no Proxmox e persistido no banco.",
        )

        return created_container


    def start(
        self,
        container_id
    ):

        started_at = perf_counter()
        container = self._get_container_or_fail(
            container_id
        )

        if (
            container.status
            ==
            "running"
        ):
            raise ValueError(
                "Container já iniciado"
            )

        operation = (
            self.proxmox_client
            .start_container(
                container.container_number
            )
        )

        self._apply_operation_result(
            container=container,
            status=operation.status or "running",
            ip_address=operation.ip_address,
        )

        updated_container = (
            self.repository
            .update(
                container
            )
        )

        self._log_action(
            action="start",
            container=updated_container,
            started_at=started_at,
            success=operation.success,
            message=operation.message,
        )

        return self._operation_dto(
            container=updated_container,
            operation=operation.operation,
            success=operation.success,
            message=operation.message,
        )


    def stop(
        self,
        container_id
    ):

        started_at = perf_counter()
        container = self._get_container_or_fail(
            container_id
        )

        if (
            container.status
            ==
            "stopped"
        ):
            raise ValueError(
                "Container já parado"
            )

        operation = (
            self.proxmox_client
            .stop_container(
                container.container_number
            )
        )

        self._apply_operation_result(
            container=container,
            status=operation.status or "stopped",
            ip_address=operation.ip_address,
        )

        updated_container = (
            self.repository
            .update(
                container
            )
        )

        self._log_action(
            action="stop",
            container=updated_container,
            started_at=started_at,
            success=operation.success,
            message=operation.message,
        )

        return self._operation_dto(
            container=updated_container,
            operation=operation.operation,
            success=operation.success,
            message=operation.message,
        )


    def restart(
        self,
        container_id
    ):

        started_at = perf_counter()
        container = self._get_container_or_fail(
            container_id
        )

        operation = (
            self.proxmox_client
            .restart_container(
                container.container_number
            )
        )

        self._apply_operation_result(
            container=container,
            status=operation.status or "running",
            ip_address=operation.ip_address,
        )

        updated_container = (
            self.repository
            .update(
                container
            )
        )

        self._log_action(
            action="restart",
            container=updated_container,
            started_at=started_at,
            success=operation.success,
            message=operation.message,
        )

        return self._operation_dto(
            container=updated_container,
            operation=operation.operation,
            success=operation.success,
            message=operation.message,
        )


    def delete(
        self,
        container_id
    ):

        started_at = perf_counter()
        container = self._get_container_or_fail(
            container_id
        )

        operation = (
            self.proxmox_client
            .delete_container(
                container.container_number
            )
        )

        self._apply_operation_result(
            container=container,
            status=operation.status or "deleted",
            ip_address=operation.ip_address,
        )

        updated_container = (
            self.repository
            .update(
                container
            )
        )

        self._log_action(
            action="delete",
            container=updated_container,
            started_at=started_at,
            success=operation.success,
            message=operation.message,
        )

        return ContainerOperationDTO(
            container_id=updated_container.id,
            container_number=updated_container.container_number,
            operation=operation.operation,
            success=operation.success,
            message=operation.message,
            status=updated_container.status,
        )


    def get_status(
        self,
        container_id
    ):

        container = self._get_container_or_fail(
            container_id
        )

        proxmox_status = (
            self.proxmox_client
            .get_container_status(
                container.container_number
            )
        )

        return ContainerStatusDTO(
            container_id=container.id,
            container_number=container.container_number,
            status=container.status,
            proxmox_status=proxmox_status.status,
            uptime_seconds=proxmox_status.uptime_seconds,
            cpu_usage_percent=proxmox_status.cpu_usage_percent,
            memory_usage_mb=proxmox_status.memory_usage_mb,
        )


    def sync(
        self,
        container_id
    ):

        started_at = perf_counter()
        container = self._get_container_or_fail(
            container_id
        )

        proxmox_container = (
            self.proxmox_client
            .get_container(
                container.container_number
            )
        )

        self._apply_container_info(
            container=container,
            proxmox_container=proxmox_container,
        )

        updated_container = (
            self.repository
            .update(
                container
            )
        )

        self._log_action(
            action="sync",
            container=updated_container,
            started_at=started_at,
            success=True,
            message="Container sincronizado com Proxmox.",
        )

        return updated_container


    def list(self):

        return (
            self.repository
            .list()
        )


    def get(
        self,
        container_id
    ):

        return self._get_container_or_fail(
            container_id
        )


    def _get_container_or_fail(
        self,
        container_id
    ):

        container = (
            self.repository
            .get(
                container_id
            )
        )

        if not container:
            raise ValueError(
                "Container não encontrado"
            )

        return container


    def _operation_dto(
        self,
        container: Container,
        operation: str,
        success: bool,
        message: str,
    ):

        return ContainerOperationDTO(
            container_id=container.id,
            container_number=container.container_number,
            operation=operation,
            success=success,
            message=message,
            status=container.status,
        )


    def _apply_operation_result(
        self,
        container: Container,
        status: str,
        ip_address: str | None = None,
    ):

        container.status = status

        if ip_address:
            container.ip_address = ip_address

        container.updated_at = datetime.now()


    def _apply_container_info(
        self,
        container: Container,
        proxmox_container: ContainerInfo,
    ):

        container.name = proxmox_container.name
        container.status = proxmox_container.status
        container.cpu = proxmox_container.cpu
        container.memory_mb = proxmox_container.memory_mb

        if proxmox_container.disk_gb is not None:
            container.disk_gb = proxmox_container.disk_gb

        container.ip_address = proxmox_container.ip_address
        container.image_name = proxmox_container.image_name
        container.updated_at = datetime.now()


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
                "duration_ms": round(
                    (perf_counter() - started_at) * 1000,
                    2,
                ),
                "success": success,
                "message": message,
                "status": container.status,
            },
        )
