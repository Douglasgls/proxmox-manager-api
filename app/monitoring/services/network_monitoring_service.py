from app.monitoring.dtos import NetworkInventoryDTO
from app.monitoring.inventory.network_inventory_collector import NetworkInventoryCollector


class NetworkMonitoringService:
    def __init__(self, inventory_collector: NetworkInventoryCollector):
        self.inventory_collector = inventory_collector

    def get_inventory(self) -> NetworkInventoryDTO:
        return self.inventory_collector.collect()
