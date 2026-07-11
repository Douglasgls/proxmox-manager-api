from app.integrations.proxmox import ProxmoxClient
from app.monitoring.dtos import HostMetricsDTO


class HostMetricsCollector:
    """Collects the current resource usage of the selected Proxmox node."""

    def __init__(self, proxmox_client: ProxmoxClient):
        self.proxmox_client = proxmox_client

    def collect(self) -> HostMetricsDTO:
        status = self.proxmox_client.get_node_status()
        node_summary = self._node_summary()
        memory = status.get("memory") or {}
        swap = status.get("swap") or {}
        rootfs = status.get("rootfs") or {}

        return HostMetricsDTO(
            cpu_usage_percent=self._percentage(status.get("cpu")),
            memory_used_bytes=self._int_or_none(memory.get("used")),
            memory_free_bytes=self._free_bytes(memory),
            swap_used_bytes=self._int_or_none(swap.get("used")),
            swap_free_bytes=self._free_bytes(swap),
            disk_used_bytes=self._int_or_none(rootfs.get("used")),
            disk_free_bytes=self._free_bytes(rootfs),
            rx_bytes=self._int_or_none(node_summary.get("netin") or status.get("netin")),
            tx_bytes=self._int_or_none(node_summary.get("netout") or status.get("netout")),
            load_average=self._load_average(status.get("loadavg")),
            uptime_seconds=self._int_or_none(status.get("uptime")),
        )

    def _node_summary(self) -> dict:
        for node in self.proxmox_client.list_nodes():
            if node.get("node") == self.proxmox_client.node:
                return node
        return {}

    def _free_bytes(self, data: dict) -> int | None:
        free = self._int_or_none(data.get("free") or data.get("avail"))
        if free is not None:
            return free
        total = self._int_or_none(data.get("total"))
        used = self._int_or_none(data.get("used"))
        return total - used if total is not None and used is not None else None

    @staticmethod
    def _percentage(value) -> float | None:
        try:
            return round(float(value) * 100, 2) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _load_average(value) -> list[float]:
        if not isinstance(value, (list, tuple)):
            return []
        return [float(item) for item in value]

    @staticmethod
    def _int_or_none(value) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
