import logging
from time import perf_counter

from app.dto.response.container import ContainerOperationDTO, ContainerStatusDTO
from app.integrations.proxmox import ProxmoxClient
from app.models.container import Container
from app.models.network_configuration import NetworkConfiguration
from app.provision.engine import ProvisionEngine
from app.provision.plan import ProvisionPlan
from app.repositories.container_repository import ContainerRepository
from app.services.audit_log_service import AuditLogService
from app.services.container.container_lifecycle_service import ContainerLifecycleService
from app.services.container.container_network_service import ContainerNetworkService
from app.services.container.container_sync_service import ContainerSyncService

logger = logging.getLogger(__name__)


class ContainerService:
    """Facade unificado para gerenciamento de containers LXC.
    
    Delegando responsabilidades para os sub-serviços especializados:
    - ContainerNetworkService (construção e validação de rede)
    - ContainerSyncService (sincronização de estado runtime com Proxmox)
    - ContainerLifecycleService (criação, ciclo de vida e destruição)
    """

    def __init__(
        self,
        repository: ContainerRepository,
        proxmox_client: ProxmoxClient,
        audit_log_service: AuditLogService | None = None,
        provision_engine: ProvisionEngine | None = None,
    ):
        self.repository = repository
        self.proxmox_client = proxmox_client
        self.audit_log_service = audit_log_service
        self.provision_engine = provision_engine or ProvisionEngine()

        self.network_service = ContainerNetworkService()
        self.sync_service = ContainerSyncService(
            repository=self.repository,
            proxmox_client=self.proxmox_client,
            audit_log_service=self.audit_log_service,
        )
        self.lifecycle_service = ContainerLifecycleService(
            repository=self.repository,
            proxmox_client=self.proxmox_client,
            network_service=self.network_service,
            sync_service=self.sync_service,
            audit_log_service=self.audit_log_service,
            provision_engine=self.provision_engine,
        )

    def create(
        self,
        name,
        password,
        cpu,
        memory_mb,
        disk_gb=2,
        image_name=None,
        bridge="vmbr0",
        ip_mode="dhcp",
        ip_address=None,
        cidr=None,
        gateway=None,
        firewall=False,
        mtu=None,
        vlan=None,
        mac_address=None,
        provision_plan: ProvisionPlan | None = None,
        lifecycle_callbacks: dict | None = None,
        provision_callbacks: dict | None = None,
        created_by: str | None = None,
    ) -> Container:
        return self.lifecycle_service.create(
            name=name,
            password=password,
            cpu=cpu,
            memory_mb=memory_mb,
            disk_gb=disk_gb,
            image_name=image_name,
            bridge=bridge,
            ip_mode=ip_mode,
            ip_address=ip_address,
            cidr=cidr,
            gateway=gateway,
            firewall=firewall,
            mtu=mtu,
            vlan=vlan,
            mac_address=mac_address,
            provision_plan=provision_plan,
            lifecycle_callbacks=lifecycle_callbacks,
            provision_callbacks=provision_callbacks,
            created_by=created_by,
        )

    def start(self, container_id) -> ContainerOperationDTO:
        container = self._get_container_or_fail(container_id)
        return self.lifecycle_service.start(container)

    def stop(self, container_id) -> ContainerOperationDTO:
        container = self._get_container_or_fail(container_id)
        return self.lifecycle_service.stop(container)

    def restart(self, container_id) -> ContainerOperationDTO:
        container = self._get_container_or_fail(container_id)
        return self.lifecycle_service.restart(container)

    def delete(self, container_id) -> ContainerOperationDTO:
        container = self._get_container_or_fail(container_id)
        return self.lifecycle_service.delete(container)

    def get_status(self, container_id) -> ContainerStatusDTO:
        container = self._get_container_or_fail(container_id)
        return self.sync_service.get_status(container)

    def sync(self, container_id) -> Container:
        container = self._get_container_or_fail(container_id)
        return self.sync_service.sync(container)

    def sync_all(self) -> list[Container]:
        return self.sync_service.sync_all()

    def list(self) -> list[Container]:
        return self.repository.list()

    def get(self, container_id) -> Container:
        return self._get_container_or_fail(container_id)

    def list_networks(self):
        return self.proxmox_client.list_networks()

    def update_network(self, container_id, **network_data) -> Container:
        started_at = perf_counter()
        container = self._get_container_or_fail(container_id)
        network = self.network_service.build_network_from_container(
            container=container,
            network_data=network_data,
        )

        operation = self.proxmox_client.update_container_network(
            container_id=container.container_number,
            network=network,
        )

        self.network_service.apply_network_configuration(
            container=container,
            network=network,
        )
        container.status = operation.status or container.status
        if operation.ip_address or network.ip_address:
            container.ip_address = operation.ip_address or network.ip_address

        updated_container = self.repository.update(container)

        if self.audit_log_service:
            self.audit_log_service.log(
                entity="container",
                entity_id=updated_container.id,
                action="update_network",
                details={
                    "container_number": updated_container.container_number,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    "success": operation.success,
                    "message": operation.message,
                    "status": updated_container.status,
                },
            )

        return updated_container

    # Métodos privados utilitários mantidos para retrocompatibilidade
    def _get_container_or_fail(self, container_id) -> Container:
        container = self.repository.get(container_id)
        if not container:
            raise ValueError("Container não encontrado")
        return container

    def _sync_container_runtime(self, container: Container, status_info=None) -> Container:
        return self.sync_service.sync_container_runtime(container, status_info=status_info)

    def _build_network(self, **kwargs) -> NetworkConfiguration:
        return self.network_service.build_network(**kwargs)

    def _apply_network_configuration(self, container: Container, network: NetworkConfiguration):
        self.network_service.apply_network_configuration(container, network)
