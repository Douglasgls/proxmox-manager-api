import logging
from app.core.dependencies import get_proxmox_client
from app.services.monitoring.host_monitoring_service import HostMonitoringService
from app.services.monitoring.container_monitoring_service import ContainerMonitoringService
from app.services.monitoring.collectors.inventory.host_inventory_collector import HostInventoryCollector
from app.services.monitoring.collectors.metrics.host_metrics_collector import HostMetricsCollector
from app.services.monitoring.collectors.inventory.container_inventory_collector import ContainerInventoryCollector
from app.services.monitoring.collectors.metrics.container_metrics_collector import ContainerMetricsCollector
from app.services.monitoring.tasks.publisher import MonitoringPublisher
from app.services.monitoring.tasks.scheduler import MonitoringScheduler

logger = logging.getLogger(__name__)

class MetricsCollector:
    """Adapter class to keep backward compatibility with main.py, running the new Scheduler."""

    def __init__(self):
        self.scheduler = None

    async def start(self):
        logger.info("Initializing and starting the new MonitoringScheduler via MetricsCollector adapter...")
        try:
            proxmox_client = get_proxmox_client()
            host_service = HostMonitoringService(
                inventory_collector=HostInventoryCollector(proxmox_client),
                metrics_collector=HostMetricsCollector(proxmox_client),
            )
            container_service = ContainerMonitoringService(
                inventory_collector=ContainerInventoryCollector(proxmox_client),
                metrics_collector=ContainerMetricsCollector(proxmox_client),
            )
            publisher = MonitoringPublisher(
                host_service=host_service,
                container_service=container_service,
            )
            self.scheduler = MonitoringScheduler(publisher)
            await self.scheduler.start()
        except Exception as e:
            logger.error(f"Failed to start MetricsCollector adapter: {e}", exc_info=True)
            raise

    async def stop(self):
        logger.info("Stopping MetricsCollector adapter...")
        if self.scheduler:
            await self.scheduler.stop()

metrics_collector = MetricsCollector()
