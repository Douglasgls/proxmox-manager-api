import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.core.event_bus import event_bus
from app.services.monitoring.container_monitoring_service import ContainerMonitoringService
from app.services.monitoring.host_monitoring_service import HostMonitoringService

logger = logging.getLogger(__name__)

class MonitoringPublisher:
    """Publisher responsible for pushing monitoring events to the EventBus."""

    def __init__(
        self,
        host_service: HostMonitoringService,
        container_service: ContainerMonitoringService,
    ):
        self.host_service = host_service
        self.container_service = container_service

        # State for host network rate calculation (dashboard metrics)
        self.prev_rx_bytes: Optional[int] = None
        self.prev_tx_bytes: Optional[int] = None
        self.prev_time: Optional[datetime] = None

        # State for container status change detection (legacy channels)
        self.prev_container_statuses = {}

    async def publish_dashboard_metrics(self):
        """Collect and publish dashboard metrics to 'dashboard.metrics' channel."""
        logger.info("Publishing dashboard metrics...")
        loop = asyncio.get_running_loop()
        
        host_metrics = await loop.run_in_executor(None, self.host_service.get_metrics)
        container_inventory = await loop.run_in_executor(None, self.container_service.get_inventory)
        
        current_time = datetime.now()
        rx_rate = 0.0
        tx_rate = 0.0
        
        if (
            self.prev_time is not None
            and self.prev_rx_bytes is not None
            and self.prev_tx_bytes is not None
        ):
            dt = (current_time - self.prev_time).total_seconds()
            if dt > 0:
                if host_metrics.rx_bytes is not None:
                    rx_diff = max(0, host_metrics.rx_bytes - self.prev_rx_bytes)
                    rx_rate = round(rx_diff / dt, 2)
                if host_metrics.tx_bytes is not None:
                    tx_diff = max(0, host_metrics.tx_bytes - self.prev_tx_bytes)
                    tx_rate = round(tx_diff / dt, 2)

        # Update state
        self.prev_time = current_time
        if host_metrics.rx_bytes is not None:
            self.prev_rx_bytes = host_metrics.rx_bytes
        if host_metrics.tx_bytes is not None:
            self.prev_tx_bytes = host_metrics.tx_bytes

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
                "containers_running": container_inventory.running,
                "containers_stopped": container_inventory.stopped,
                "containers_total": container_inventory.total,
                "uptime_seconds": host_metrics.uptime_seconds or 0,
            }
        }
        await event_bus.publish("dashboard.metrics", dashboard_payload)
        if event_bus.has_subscribers("dashboard"):
            await event_bus.publish("dashboard", dashboard_payload)

    async def publish_host_metrics(self):
        """Collect and publish host metrics to 'host.metrics' channel."""
        logger.info("Publishing host metrics...")
        loop = asyncio.get_running_loop()
        host_metrics = await loop.run_in_executor(None, self.host_service.get_metrics)
        
        payload = {
            "event": "host.metrics.updated",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": host_metrics.model_dump()
        }
        await event_bus.publish("host.metrics", payload)

    async def publish_all_container_metrics(self):
        """Collect and publish all containers' metrics to 'containers.metrics' channel."""
        logger.info("Publishing all container metrics...")
        loop = asyncio.get_running_loop()
        all_metrics = await loop.run_in_executor(None, self.container_service.get_metrics)
        
        payload = {
            "event": "containers.metrics.updated",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": [m.model_dump() for m in all_metrics]
        }
        await event_bus.publish("containers.metrics", payload)

        # Legacy 'containers' channel status updates
        if event_bus.has_subscribers("containers"):
            current_statuses = {}
            for m in all_metrics:
                cid = m.container_id
                status = m.status
                current_statuses[cid] = status
                
                # If status changed or it's a newly discovered container, publish event to 'containers' channel
                if self.prev_container_statuses.get(cid) != status:
                    container_payload = {
                        "event": "container.updated",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "data": {
                            "container_id": cid,
                            "status": status or "unknown"
                        }
                    }
                    await event_bus.publish("containers", container_payload)
            self.prev_container_statuses = current_statuses



    async def publish_container_metrics(self, container_id: int):
        """Collect and publish metrics for a specific container."""
        logger.info(f"Publishing metrics for container {container_id}...")
        loop = asyncio.get_running_loop()
        try:
            metrics = await loop.run_in_executor(
                None, self.container_service.get_container_metrics, container_id
            )
            payload = {
                "event": f"containers.{container_id}.metrics.updated",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": metrics.model_dump()
            }
            await event_bus.publish(f"containers.{container_id}.metrics", payload)
        except Exception as e:
            logger.error(f"Error publishing container {container_id} metrics: {e}", exc_info=True)
