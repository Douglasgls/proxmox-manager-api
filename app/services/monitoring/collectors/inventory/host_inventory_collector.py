from app.integrations.proxmox import ProxmoxClient
from app.dto.response.monitoring import HostInventoryDTO


class HostInventoryCollector:
    """Collects the mostly static inventory of the selected Proxmox node."""

    def __init__(self, proxmox_client: ProxmoxClient):
        self.proxmox_client = proxmox_client

    def collect(self) -> HostInventoryDTO:
        status = self.proxmox_client.get_node_status()
        version = self.proxmox_client.get_version()
        containers = self.proxmox_client.list_container_runtime_data()
        templates = self.proxmox_client.list_storage_content("vztmpl")
        isos = self.proxmox_client.list_storage_content("iso")
        cpu_info = status.get("cpuinfo") or {}

        return HostInventoryDTO(
            hostname=status.get("node") or self.proxmox_client.node,
            proxmox_version=status.get("pveversion") or version.get("version"),
            kernel_version=status.get("kversion"),
            architecture=cpu_info.get("arch") or status.get("arch"),
            cpu_model=cpu_info.get("model"),
            cpu_cores=self._int_or_none(cpu_info.get("cores")),
            cpu_threads=self._int_or_none(cpu_info.get("cpus")),
            memory_total_bytes=self._int_or_none((status.get("memory") or {}).get("total")),
            swap_total_bytes=self._int_or_none((status.get("swap") or {}).get("total")),
            containers_total=len(containers),
            containers_running=self._count_status(containers, "running"),
            containers_stopped=self._count_status(containers, "stopped"),
            containers_locked=sum(bool(item.get("lock")) for item in containers),
            containers_suspended=self._count_status(containers, "suspended"),
            iso_count=len(isos),
            template_count=len(templates),
        )

    @staticmethod
    def _count_status(containers: list[dict], status: str) -> int:
        return sum(item.get("status") == status for item in containers)

    @staticmethod
    def _int_or_none(value) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
