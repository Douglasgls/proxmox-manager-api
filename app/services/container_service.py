from datetime import datetime
from ipaddress import ip_address as parse_ip_address
import re
from time import perf_counter

from app.core.exceptions import DomainValidationError
from app.models.container import (
    Container
)
from app.models.network_configuration import (
    NetworkConfiguration,
    NetworkIpMode,
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
    ):

        started_at = perf_counter()
        network = self._build_network(
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
                network=network,
                disk_gb=disk_gb,
                image_name=image_name,
                password=password
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
            password=password,
            created_by="fe82e4f9-b04e-4946-93bc-d1145f313eb1",
        )
        self._apply_network_configuration(
            container=container,
            network=network,
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

        # TODO: retornar um json com a mensagem de erro, ao invés de lançar uma exceção. Isso facilitaria o tratamento do erro no front-end.

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


    def list_networks(self):
        print(type(self.proxmox_client))
        print(self.proxmox_client.__class__)
        print(self.proxmox_client.__module__)
        print([m for m in dir(self.proxmox_client) if "list_networks" in m.lower()])
        print("list_networks called", self.proxmox_client.list_networks())
        return (
            self.proxmox_client
            .list_networks()
        )


    def update_network(
        self,
        container_id,
        **network_data,
    ):

        started_at = perf_counter()
        container = self._get_container_or_fail(
            container_id
        )
        network = self._build_network_from_container(
            container=container,
            network_data=network_data,
        )

        operation = (
            self.proxmox_client
            .update_container_network(
                container_id=container.container_number,
                network=network,
            )
        )

        self._apply_network_configuration(
            container=container,
            network=network,
        )
        self._apply_operation_result(
            container=container,
            status=operation.status or container.status,
            ip_address=(
                operation.ip_address
                or network.ip_address
            ),
        )

        updated_container = (
            self.repository
            .update(
                container
            )
        )

        self._log_action(
            action="update_network",
            container=updated_container,
            started_at=started_at,
            success=operation.success,
            message=operation.message,
        )

        return updated_container


# Private
# TODO: Todas as validações precisam ser refatoradas para validar tudo de uma vez só, ao invés de validar campo por campo. 

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


    def _build_network_from_container(
        self,
        container: Container,
        network_data: dict,
    ) -> NetworkConfiguration:

        values = self._current_network_values(
            container
        )

        if (
            network_data.get("ip_mode")
            ==
            NetworkIpMode.DHCP.value
            and
            not self._has_static_fields(network_data)
        ):
            values.update(
                self._empty_static_values()
            )

        values.update(
            network_data
        )

        return self._build_network(
            **values
        )


    def _current_network_values(
        self,
        container: Container,
    ) -> dict:

        ip_mode = container.ip_mode or NetworkIpMode.DHCP.value

        return {
            "bridge": container.bridge or "vmbr0",
            "ip_mode": ip_mode,
            "ip_address": self._current_static_value(
                ip_mode,
                container.ip_address,
            ),
            "cidr": self._current_static_value(
                ip_mode,
                container.cidr,
            ),
            "gateway": self._current_static_value(
                ip_mode,
                container.gateway,
            ),
            "firewall": container.firewall,
            "mtu": container.mtu,
            "vlan": container.vlan,
            "mac_address": container.mac_address,
        }


    def _current_static_value(
        self,
        ip_mode: str,
        value,
    ):

        if ip_mode == NetworkIpMode.DHCP.value:
            return None

        return value


    def _empty_static_values(
        self,
    ) -> dict:

        return {
            "ip_address": None,
            "cidr": None,
            "gateway": None,
        }


    def _has_static_fields(
        self,
        network_data: dict,
    ) -> bool:

        return any(
            network_data.get(field) is not None
            for field in (
                "ip_address",
                "cidr",
                "gateway",
            )
        )


    def _build_network(
        self,
        bridge,
        ip_mode,
        ip_address=None,
        cidr=None,
        gateway=None,
        firewall=False,
        mtu=None,
        vlan=None,
        mac_address=None,
    ) -> NetworkConfiguration:

        network = NetworkConfiguration(
            bridge=bridge,
            ip_mode=self._network_ip_mode(ip_mode),
            ip_address=ip_address,
            cidr=cidr,
            gateway=gateway,
            firewall=bool(firewall),
            mtu=mtu,
            vlan=vlan,
            mac_address=mac_address,
        )

        self._validate_network(
            network
        )

        return network


    def _network_ip_mode(
        self,
        ip_mode,
    ) -> NetworkIpMode:

        try:
            return NetworkIpMode(
                ip_mode
            )
        except ValueError as exc:
            raise DomainValidationError(
                "Modo de IP inválido. Use 'dhcp' ou 'static'."
            ) from exc


    def _validate_network(
        self,
        network: NetworkConfiguration,
    ):

        if not network.bridge:
            raise DomainValidationError(
                "Bridge de rede é obrigatória"
            )

        validators = {
            NetworkIpMode.DHCP: self._validate_dhcp,
            NetworkIpMode.STATIC: self._validate_static,
        }
        validators[network.ip_mode](
            network
        )

        self._validate_optional_network_fields(
            network
        )


    def _validate_dhcp(
        self,
        network: NetworkConfiguration,
    ):

        if (
            network.ip_address
            or network.gateway
            or network.cidr is not None
        ):
            raise DomainValidationError(
                "Configuração DHCP não permite ip_address, gateway ou cidr"
            )


    def _validate_static(
        self,
        network: NetworkConfiguration,
    ):

        missing = [
            field
            for field, value in {
                "ip_address": network.ip_address,
                "gateway": network.gateway,
                "cidr": network.cidr,
            }.items()
            if value is None
        ]

        if missing:
            raise DomainValidationError(
                "Configuração static exige: "
                + ", ".join(missing)
            )

        self._validate_ip_address(
            "ip_address",
            network.ip_address,
        )
        self._validate_ip_address(
            "gateway",
            network.gateway,
        )
        self._validate_cidr(
            network.cidr
        )


    def _validate_optional_network_fields(
        self,
        network: NetworkConfiguration,
    ):

        if network.mtu is not None and network.mtu <= 0:
            raise DomainValidationError(
                "MTU deve ser maior que zero"
            )

        if network.vlan is not None and not 1 <= network.vlan <= 4094:
            raise DomainValidationError(
                "VLAN deve estar entre 1 e 4094"
            )

        self._validate_mac_address(
            network.mac_address
        )


    def _validate_ip_address(
        self,
        field_name: str,
        value: str | None,
    ):

        try:
            parse_ip_address(
                value
            )
        except ValueError as exc:
            raise DomainValidationError(
                f"{field_name} inválido"
            ) from exc


    def _validate_cidr(
        self,
        cidr: int | None,
    ):

        if cidr is None:
            return

        if not 0 <= cidr <= 32:
            raise DomainValidationError(
                "CIDR deve estar entre 0 e 32"
            )


    def _validate_mac_address(
        self,
        mac_address: str | None,
    ):

        if mac_address is None:
            return

        if not re.fullmatch(
            r"[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}",
            mac_address,
        ):
            raise DomainValidationError(
                "MAC address inválido"
            )


    def _apply_network_configuration(
        self,
        container: Container,
        network: NetworkConfiguration,
    ):

        container.bridge = network.bridge
        container.ip_mode = network.ip_mode.value
        container.ip_address = network.ip_address
        container.cidr = network.cidr
        container.gateway = network.gateway
        container.firewall = network.firewall
        container.mtu = network.mtu
        container.vlan = network.vlan
        container.mac_address = network.mac_address


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
