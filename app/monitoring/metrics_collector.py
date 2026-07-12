import asyncio
from datetime import datetime
import logging
from app.core.event_bus import event_bus
from app.core.dependencies import get_proxmox_client
from app.monitoring.metrics.host_metrics_collector import HostMetricsCollector
from app.monitoring.metrics.container_metrics_collector import ContainerMetricsCollector

logger = logging.getLogger(__name__)

class MetricsCollector:
    def __init__(self, interval_seconds: float = 2.0):
        self.interval_seconds = interval_seconds
        self.running = False
        self._task = None
        
        # State for host network rate calculation
        self.prev_rx_bytes = None
        self.prev_tx_bytes = None
        self.prev_time = None
        
        # State for container status change detection
        self.prev_container_statuses = {}

    async def start(self):
        self.running = True
        logger.info("Starting MetricsCollector background loop...")
        while self.running:
            try:
                await self.collect_and_publish()
            except Exception as e:
                logger.error(f"Error in MetricsCollector background loop: {e}", exc_info=True)
            # Sleep until next cycle
            await asyncio.sleep(self.interval_seconds)

    async def stop(self):
        self.running = False
        logger.info("Stopping MetricsCollector background loop...")

    async def collect_and_publish(self):
        proxmox_client = get_proxmox_client()
        
        loop = asyncio.get_running_loop()
        
        # Collect host metrics and container runtime data in executors to prevent blocking the event loop
        host_collector = HostMetricsCollector(proxmox_client)
        host_metrics = await loop.run_in_executor(None, host_collector.collect)
        
        raw_containers = await loop.run_in_executor(None, proxmox_client.list_container_runtime_data)
        
        # 1. Process Host Metrics
        current_time = datetime.now()
        rx_rate = 0.0
        tx_rate = 0.0
        
        if self.prev_time is not None and self.prev_rx_bytes is not None and self.prev_tx_bytes is not None:
            dt = (current_time - self.prev_time).total_seconds()
            if dt > 0:
                if host_metrics.rx_bytes is not None:
                    rx_diff = max(0, host_metrics.rx_bytes - self.prev_rx_bytes)
                    rx_rate = round(rx_diff / dt, 2)
                if host_metrics.tx_bytes is not None:
                    tx_diff = max(0, host_metrics.tx_bytes - self.prev_tx_bytes)
                    tx_rate = round(tx_diff / dt, 2)

        # Update previous values
        self.prev_time = current_time
        if host_metrics.rx_bytes is not None:
            self.prev_rx_bytes = host_metrics.rx_bytes
        if host_metrics.tx_bytes is not None:
            self.prev_tx_bytes = host_metrics.tx_bytes

        # Calculate percentages
        memory_usage_percent = 0.0
        if host_metrics.memory_used_bytes is not None and host_metrics.memory_free_bytes is not None:
            total_mem = host_metrics.memory_used_bytes + host_metrics.memory_free_bytes
            if total_mem > 0:
                memory_usage_percent = round((host_metrics.memory_used_bytes / total_mem) * 100, 2)

        disk_usage_percent = 0.0
        if host_metrics.disk_used_bytes is not None and host_metrics.disk_free_bytes is not None:
            total_disk = host_metrics.disk_used_bytes + host_metrics.disk_free_bytes
            if total_disk > 0:
                disk_usage_percent = round((host_metrics.disk_used_bytes / total_disk) * 100, 2)

        # Count container statuses
        containers_total = len(raw_containers)
        containers_running = sum(1 for c in raw_containers if c.get("status") == "running")
        containers_stopped = sum(1 for c in raw_containers if c.get("status") == "stopped")
        
        # Publish dashboard metrics
        dashboard_payload = {
            "event": "dashboard.metrics.updated",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "cpu_usage_percent": host_metrics.cpu_usage_percent or 0.0,
                "memory_usage_percent": memory_usage_percent,
                "memory_used_bytes": host_metrics.memory_used_bytes or 0,
                "disk_usage_percent": disk_usage_percent,
                "network_rx_rate": rx_rate,
                "network_tx_rate": tx_rate,
                "containers_running": containers_running,
                "containers_stopped": containers_stopped,
                "containers_total": containers_total,
                "uptime_seconds": host_metrics.uptime_seconds or 0,
            }
        }
        await event_bus.publish("dashboard", dashboard_payload)
        
        # 2. Process Container updates
        current_container_statuses = {}
        for container in raw_containers:
            cid = container.get("vmid")
            status = container.get("status")
            if cid is not None:
                # Convert to int if it's string, e.g. "101"
                try:
                    cid_int = int(cid)
                except (ValueError, TypeError):
                    cid_int = cid
                
                current_container_statuses[cid_int] = status
                
                # If status changed or it's a newly discovered container, publish event
                if self.prev_container_statuses.get(cid_int) != status:
                    container_payload = {
                        "event": "container.updated",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "data": {
                            "container_id": cid_int,
                            "status": status or "unknown"
                        }
                    }
                    await event_bus.publish("containers", container_payload)

        self.prev_container_statuses = current_container_statuses

metrics_collector = MetricsCollector()
