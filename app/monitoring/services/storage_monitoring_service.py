from app.monitoring.dtos import StorageInventoryDTO
from app.monitoring.inventory.storage_inventory_collector import StorageInventoryCollector


class StorageMonitoringService:
    def __init__(self, inventory_collector: StorageInventoryCollector):
        self.inventory_collector = inventory_collector

    def get_inventory(self) -> list[StorageInventoryDTO]:
        return self.inventory_collector.collect()
