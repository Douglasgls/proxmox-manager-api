from app.dto.response.monitoring import HostInventoryDTO, HostMetricsDTO
from app.services.monitoring.collectors.inventory.host_inventory_collector import HostInventoryCollector
from app.services.monitoring.collectors.metrics.host_metrics_collector import HostMetricsCollector


class HostMonitoringService:
    def __init__(
        self,
        inventory_collector: HostInventoryCollector,
        metrics_collector: HostMetricsCollector,
    ):
        self.inventory_collector = inventory_collector
        self.metrics_collector = metrics_collector

    def get_inventory(self) -> HostInventoryDTO:
        return self.inventory_collector.collect()

    def get_metrics(self) -> HostMetricsDTO:
        return self.metrics_collector.collect()
