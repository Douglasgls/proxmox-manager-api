from app.integrations.proxmox import ProxmoxClient
from app.dto.response.monitoring import NetworkInterfaceDTO, NetworkInventoryDTO


class NetworkInventoryCollector:
    """Collects node network interfaces and identifies bridge interfaces."""

    BRIDGE_TYPES = {"bridge", "ovsbridge"}

    def __init__(self, proxmox_client: ProxmoxClient):
        self.proxmox_client = proxmox_client

    def collect(self) -> NetworkInventoryDTO:
        interfaces = [
            self._to_dto(interface)
            for interface in self.proxmox_client.list_network_interfaces()
        ]
        bridges = [
            interface
            for interface in interfaces
            if (interface.interface_type or "").lower() in self.BRIDGE_TYPES
        ]

        return NetworkInventoryDTO(bridges=bridges, interfaces=interfaces)

    def _to_dto(self, data: dict) -> NetworkInterfaceDTO:
        return NetworkInterfaceDTO(
            name=data.get("iface") or data.get("name") or "unknown",
            interface_type=data.get("type"),
            active=self._as_bool(data.get("active")),
            address=data.get("address"),
            netmask=data.get("netmask"),
            gateway=data.get("gateway"),
        )

    @staticmethod
    def _as_bool(value) -> bool:
        return str(value).lower() in {"1", "true", "yes"}
