from app.integrations.proxmox import ContainerNotFoundError, ProxmoxClient
from app.monitoring.dtos import ContainerInventoryDTO, ContainerInventorySummaryDTO


class ContainerInventoryCollector:
    """Collects static LXC inventory without accessing application storage."""

    def __init__(self, proxmox_client: ProxmoxClient):
        self.proxmox_client = proxmox_client

    def collect_all(self) -> ContainerInventorySummaryDTO:
        containers = [
            self._to_dto(item)
            for item in self.proxmox_client.list_container_runtime_data()
        ]

        return ContainerInventorySummaryDTO(
            containers=containers,
            total=len(containers),
            running=sum(item.status == "running" for item in containers),
            stopped=sum(item.status == "stopped" for item in containers),
            locked=sum(item.locked for item in containers),
            suspended=sum(item.status == "suspended" for item in containers),
        )

    def collect_one(self, container_id: int) -> ContainerInventoryDTO:
        for container in self.proxmox_client.list_container_runtime_data():
            if self._int_or_none(container.get("vmid")) == container_id:
                return self._to_dto(container)

        raise ContainerNotFoundError(f"Container {container_id} not found")

    def _to_dto(self, data: dict) -> ContainerInventoryDTO:
        container_id = self._int_or_none(data.get("vmid"))
        if container_id is None:
            raise ValueError("Proxmox returned a container without vmid")

        lock = data.get("lock")
        return ContainerInventoryDTO(
            container_id=container_id,
            name=data.get("name") or f"container-{container_id}",
            status=data.get("status") or "unknown",
            locked=bool(lock),
            lock=str(lock) if lock else None,
            cpu_cores=self._int_or_none(data.get("cpus") or data.get("cores")),
            memory_total_bytes=self._int_or_none(data.get("maxmem")),
            disk_total_bytes=self._int_or_none(data.get("maxdisk")),
        )

    @staticmethod
    def _int_or_none(value) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
