from app.integrations.proxmox import ProxmoxClient
from app.dto.response.monitoring import StorageInventoryDTO


class StorageInventoryCollector:
    """Collects configured Proxmox storages and their capacity metadata."""

    def __init__(self, proxmox_client: ProxmoxClient):
        self.proxmox_client = proxmox_client

    def collect(self) -> list[StorageInventoryDTO]:
        return [self._to_dto(storage) for storage in self.proxmox_client.list_storage()]

    def _to_dto(self, data: dict) -> StorageInventoryDTO:
        return StorageInventoryDTO(
            name=data.get("storage") or "unknown",
            storage_type=data.get("type"),
            active=self._as_bool(data.get("active")),
            enabled=not self._as_bool(data.get("disable")),
            shared=self._as_bool(data.get("shared")),
            content_types=self._content_types(data.get("content")),
            total_bytes=self._int_or_none(data.get("total")),
        )

    @staticmethod
    def _content_types(value) -> list[str]:
        return str(value).split(",") if value else []

    @staticmethod
    def _as_bool(value) -> bool:
        return str(value).lower() in {"1", "true", "yes"}

    @staticmethod
    def _int_or_none(value) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
