from app.integrations.proxmox import ProxmoxClient
from app.dto.response.monitoring import ContainerMetricsDTO


class ContainerMetricsCollector:
    """Collects current LXC metrics directly from Proxmox."""

    def __init__(self, proxmox_client: ProxmoxClient):
        self.proxmox_client = proxmox_client

    def collect_all(self) -> list[ContainerMetricsDTO]:
        return [
            self._to_dto(container)
            for container in self.proxmox_client.list_container_runtime_data()
        ]

    def collect_one(self, container_id: int) -> ContainerMetricsDTO:
        return self._to_dto(
            self.proxmox_client.get_container_runtime_data(container_id),
            container_id=container_id,
        )

    def _to_dto(
        self,
        data: dict,
        container_id: int | None = None,
    ) -> ContainerMetricsDTO:
        resolved_id = container_id or self._int_or_none(data.get("vmid"))
        if resolved_id is None:
            raise ValueError("Proxmox returned runtime data without vmid")

        memory_used = self._int_or_none(data.get("mem"))
        memory_total = self._int_or_none(data.get("maxmem"))
        disk_used = self._int_or_none(data.get("disk"))
        disk_total = self._int_or_none(data.get("maxdisk"))

        return ContainerMetricsDTO(
            container_id=resolved_id,
            cpu_usage_percent=self._fraction_as_percent(data.get("cpu")),
            memory_used_bytes=memory_used,
            memory_usage_percent=self._ratio_as_percent(memory_used, memory_total),
            swap_used_bytes=self._int_or_none(data.get("swap")),
            disk_used_bytes=disk_used,
            disk_usage_percent=self._ratio_as_percent(disk_used, disk_total),
            rx_bytes=self._int_or_none(data.get("netin")),
            tx_bytes=self._int_or_none(data.get("netout")),
            io_read_bytes=self._int_or_none(data.get("diskread")),
            io_write_bytes=self._int_or_none(data.get("diskwrite")),
            status=data.get("status") or "unknown",
            uptime_seconds=self._int_or_none(data.get("uptime")),
        )

    @staticmethod
    def _fraction_as_percent(value) -> float | None:
        try:
            return round(float(value) * 100, 2) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _ratio_as_percent(used: int | None, total: int | None) -> float | None:
        if used is None or not total:
            return None
        return round((used / total) * 100, 2)

    @staticmethod
    def _int_or_none(value) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
