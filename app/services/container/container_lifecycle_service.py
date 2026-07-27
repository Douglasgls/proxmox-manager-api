import logging
import time
from datetime import datetime
from time import perf_counter

from app.dto.response.container import ContainerOperationDTO
from app.integrations.proxmox import ContainerSession, ProxmoxClient
from app.models.container import Container
from app.provision.engine import ProvisionEngine
from app.provision.plan import ProvisionPlan
from app.repositories.container_repository import ContainerRepository
from app.services.audit_log_service import AuditLogService
from app.services.container.container_network_service import ContainerNetworkService
from app.services.container.container_sync_service import ContainerSyncService

logger = logging.getLogger(__name__)


class ContainerLifecycleService:
    """Serviço responsável por criação, inicialização, parada, reinício e destruição de containers LXC."""

    def __init__(
        self,
        repository: ContainerRepository,
        proxmox_client: ProxmoxClient,
        network_service: ContainerNetworkService,
        sync_service: ContainerSyncService,
        audit_log_service: AuditLogService | None = None,
        provision_engine: ProvisionEngine | None = None,
    ):
        self.repository = repository
        self.proxmox_client = proxmox_client
        self.network_service = network_service
        self.sync_service = sync_service
        self.audit_log_service = audit_log_service
        self.provision_engine = provision_engine or ProvisionEngine()

    def create(
        self,
        name: str,
        password: str,
        cpu: int,
        memory_mb: int,
        disk_gb: int = 2,
        image_name: str | None = None,
        bridge: str = "vmbr0",
        ip_mode: str = "dhcp",
        ip_address: str | None = None,
        cidr: int | None = None,
        gateway: str | None = None,
        firewall: bool = False,
        mtu: int | None = None,
        vlan: int | None = None,
        mac_address: str | None = None,
        provision_plan: ProvisionPlan | None = None,
        lifecycle_callbacks: dict | None = None,
        provision_callbacks: dict | None = None,
        created_by: str | None = None,
    ) -> Container:
        started_at = perf_counter()
        lifecycle = lifecycle_callbacks or {}

        network = self.network_service.build_network(
            bridge=bridge,
            ip_mode=ip_mode,
            ip_address=ip_address,
            cidr=cidr,
            gateway=gateway,
            firewall=firewall,
            mtu=mtu,
            vlan=vlan,
            mac_address=mac_address,
        )

        existing = self.repository.get_by_name(name)
        if existing:
            raise ValueError("Container já existe")

        logger.info("Creating container...")
        self._notify_lifecycle(lifecycle, "waiting_proxmox_task")

        proxmox_container = self.proxmox_client.create_container(
            name=name,
            cpu=cpu,
            memory_mb=memory_mb,
            network=network,
            disk_gb=disk_gb,
            image_name=image_name,
            password=password,
        )
        logger.info("Container created.")
        self._notify_lifecycle(lifecycle, "container_created", proxmox_container)

        logger.info("Starting container...")
        self._notify_lifecycle(lifecycle, "container_starting", proxmox_container)
        self.proxmox_client.start_container(proxmox_container.container_id)

        time.sleep(10)

        # Aguardar container subir
        max_attempts = 30
        status = "stopped"
        for _ in range(max_attempts):
            status_info = self.proxmox_client.get_container_status(
                proxmox_container.container_id
            )
            status = status_info.status
            if status == "running":
                break
            time.sleep(1)

        if status != "running":
            raise ValueError("Timeout aguardando container iniciar.")

        logger.info("Container started.")
        self._notify_lifecycle(lifecycle, "container_started", proxmox_container)

        container = Container(
            container_number=proxmox_container.container_id,
            name=name,
            cpu=cpu,
            memory_mb=memory_mb,
            disk_gb=proxmox_container.disk_gb or 2,
            image_name=proxmox_container.image_name,
            password=password,
            created_by=created_by,
        )
        self.network_service.apply_network_configuration(
            container=container, network=network
        )

        created_container = self.repository.create(container)
        created_container = self.sync_service.sync_container_runtime(created_container)

        self._notify_lifecycle(lifecycle, "container_persisted", created_container)

        self._log_action(
            action="create",
            container=created_container,
            started_at=started_at,
            success=True,
            message="Container criado no Proxmox e persistido no banco.",
        )

        logger.info("Criando sessão administrativa...")
        session = ContainerSession(
            proxmox_client=self.proxmox_client,
            container_id=proxmox_container.container_id,
        )

        plan = provision_plan or ProvisionPlan(
            id="default",
            name="Default Provision",
            description="Provisionamento padrão",
            components=[],
        )
        callbacks = provision_callbacks or {}

        logger.info("Provisioning components...")
        self._notify_lifecycle(lifecycle, "provisioning_started", plan)
        result = self.provision_engine.execute(
            plan=plan,
            session=session,
            on_component_install_start=callbacks.get("install_start"),
            on_component_install_finish=callbacks.get("install_finish"),
            on_component_validate_start=callbacks.get("validate_start"),
            on_component_validate_finish=callbacks.get("validate_finish"),
        )

        if not result.success:
            logger.error("Erro no provisionamento: %s", result.error)
            raise RuntimeError(result.error)

        logger.info("Provisioning completed.")
        logger.info("Container created successfully.")

        return created_container

    def start(self, container: Container) -> ContainerOperationDTO:
        started_at = perf_counter()

        try:
            container = self.sync_service.sync_container_runtime(container)
        except Exception as e:
            logger.warning(f"Initial sync failed in start operation: {e}")

        if container.status == "running":
            raise ValueError("Container já iniciado")

        operation = self.proxmox_client.start_container(
            container_id=container.container_number
        )

        max_attempts = 30
        for _ in range(max_attempts):
            try:
                status_info = self.proxmox_client.get_container_status(
                    container.container_number
                )
                if status_info.status == "running":
                    break
            except Exception as e:
                logger.warning(f"Error checking status during start wait loop: {e}")
            time.sleep(1)

        try:
            updated_container = self.sync_service.sync_container_runtime(container)
        except Exception as e:
            logger.warning(f"Final sync failed in start operation: {e}")
            container.status = "running"
            container.updated_at = datetime.now()
            updated_container = self.repository.update(container)

        logger.info("Container started.")

        self._log_action(
            action="start",
            container=updated_container,
            started_at=started_at,
            success=operation.success,
            message=operation.message,
        )

        is_published = (
            hasattr(updated_container, "tailscale_node")
            and updated_container.tailscale_node is not None
        )
        if is_published and operation.success:
            try:
                from app.core.event_bus import EnvironmentChanged, internal_event_bus
                print(f"\n[EVENT ACTION] Container publicado iniciado. Publicando EnvironmentChanged...\n")
                internal_event_bus.publish(EnvironmentChanged())
            except Exception as ev_exc:
                logger.error("Failed to publish EnvironmentChanged event after container start: %s", ev_exc)

        return self._operation_dto(
            container=updated_container,
            operation=operation.operation,
            success=operation.success,
            message=operation.message,
        )

    def stop(self, container: Container) -> ContainerOperationDTO:
        started_at = perf_counter()

        try:
            container = self.sync_service.sync_container_runtime(container)
        except Exception as e:
            logger.warning(f"Initial sync failed in stop operation: {e}")

        if container.status == "stopped":
            raise ValueError("Container já parado")

        operation = self.proxmox_client.stop_container(container.container_number)

        max_attempts = 30
        for _ in range(max_attempts):
            try:
                status_info = self.proxmox_client.get_container_status(
                    container.container_number
                )
                if status_info.status == "stopped":
                    break
            except Exception as e:
                logger.warning(f"Error checking status during stop wait loop: {e}")
            time.sleep(1)

        try:
            updated_container = self.sync_service.sync_container_runtime(container)
        except Exception as e:
            logger.warning(f"Final sync failed in stop operation: {e}")
            container.status = "stopped"
            container.updated_at = datetime.now()
            updated_container = self.repository.update(container)

        logger.info("Container stopped.")

        self._log_action(
            action="stop",
            container=updated_container,
            started_at=started_at,
            success=operation.success,
            message=operation.message,
        )

        is_published = (
            hasattr(updated_container, "tailscale_node")
            and updated_container.tailscale_node is not None
        )
        if is_published and operation.success:
            try:
                from app.core.event_bus import EnvironmentChanged, internal_event_bus
                print(f"\n[EVENT ACTION] Container publicado parado. Publicando EnvironmentChanged...\n")
                internal_event_bus.publish(EnvironmentChanged())
            except Exception as ev_exc:
                logger.error("Failed to publish EnvironmentChanged event after container stop: %s", ev_exc)

        return self._operation_dto(
            container=updated_container,
            operation=operation.operation,
            success=operation.success,
            message=operation.message,
        )

    def restart(self, container: Container) -> ContainerOperationDTO:
        started_at = perf_counter()

        try:
            container = self.sync_service.sync_container_runtime(container)
        except Exception as e:
            logger.warning(f"Initial sync failed in restart operation: {e}")

        operation = self.proxmox_client.restart_container(container.container_number)

        max_attempts = 30
        for _ in range(max_attempts):
            try:
                status_info = self.proxmox_client.get_container_status(
                    container.container_number
                )
                if status_info.status == "running":
                    break
            except Exception as e:
                logger.warning(f"Error checking status during restart wait loop: {e}")
            time.sleep(1)

        try:
            updated_container = self.sync_service.sync_container_runtime(container)
        except Exception as e:
            logger.warning(f"Final sync failed in restart operation: {e}")
            container.status = "running"
            container.updated_at = datetime.now()
            updated_container = self.repository.update(container)

        self._log_action(
            action="restart",
            container=updated_container,
            started_at=started_at,
            success=operation.success,
            message=operation.message,
        )

        is_published = (
            hasattr(updated_container, "tailscale_node")
            and updated_container.tailscale_node is not None
        )
        if is_published and operation.success:
            try:
                from app.core.event_bus import EnvironmentChanged, internal_event_bus
                print(f"\n[EVENT ACTION] Container publicado reiniciado. Publicando EnvironmentChanged...\n")
                internal_event_bus.publish(EnvironmentChanged())
            except Exception as ev_exc:
                logger.error("Failed to publish EnvironmentChanged event after container restart: %s", ev_exc)

        return self._operation_dto(
            container=updated_container,
            operation=operation.operation,
            success=operation.success,
            message=operation.message,
        )

    def delete(self, container: Container) -> ContainerOperationDTO:
        started_at = perf_counter()

        try:
            container = self.sync_service.sync_container_runtime(container)
        except Exception as e:
            logger.warning(f"Initial sync failed in delete operation: {e}")

        operation = self.proxmox_client.delete_container(container.container_number)

        is_published = (
            hasattr(container, "tailscale_node") and container.tailscale_node is not None
        )

        container_id_val = container.id
        container_num_val = container.container_number

        self._log_action(
            action="delete",
            container=container,
            started_at=started_at,
            success=operation.success,
            message=operation.message,
        )

        self.repository.delete(container)

        if is_published:
            try:
                from app.core.event_bus import EnvironmentChanged, internal_event_bus
                print("\n[EVENT ACTION] Container publicado deletado. Publicando EnvironmentChanged...\n")
                internal_event_bus.publish(EnvironmentChanged())
            except Exception as ev_exc:
                logger.error("Failed to publish EnvironmentChanged event after container deletion: %s", ev_exc)

        return ContainerOperationDTO(
            container_id=container_id_val,
            container_number=container_num_val,
            operation=operation.operation,
            success=operation.success,
            message=operation.message,
            status="deleted",
        )

    def _notify_lifecycle(
        self,
        lifecycle_callbacks: dict,
        event: str,
        value=None,
    ):
        callback = lifecycle_callbacks.get(event)
        if callback:
            callback(value)

    def _operation_dto(
        self,
        container: Container,
        operation: str,
        success: bool,
        message: str,
    ) -> ContainerOperationDTO:
        return ContainerOperationDTO(
            container_id=container.id,
            container_number=container.container_number,
            operation=operation,
            success=success,
            message=message,
            status=container.status,
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
