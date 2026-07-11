from app.monitoring.dtos import (
    ContainerInventoryDTO,
    ContainerInventorySummaryDTO,
    ContainerMetricsDTO,
)
from app.monitoring.inventory.container_inventory_collector import ContainerInventoryCollector
from app.monitoring.metrics.container_metrics_collector import ContainerMetricsCollector

# TODO: Lembrar de alterar esses arquivos para a pasta service geral depois 
class ContainerMonitoringService:
    def __init__(
        self,
        inventory_collector: ContainerInventoryCollector,
        metrics_collector: ContainerMetricsCollector,
    ):
        self.inventory_collector = inventory_collector
        self.metrics_collector = metrics_collector

    def get_inventory(self) -> ContainerInventorySummaryDTO:
        return self.inventory_collector.collect_all()

    def get_container_inventory(self, container_id: int) -> ContainerInventoryDTO:
        return self.inventory_collector.collect_one(container_id)

    def get_metrics(self) -> list[ContainerMetricsDTO]:
        return self.metrics_collector.collect_all()

    def get_container_metrics(self, container_id: int) -> ContainerMetricsDTO:
        return self.metrics_collector.collect_one(container_id)
