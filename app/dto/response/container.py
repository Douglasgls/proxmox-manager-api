from pydantic import BaseModel
from pydantic import ConfigDict


class ContainerResponseDTO(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: str
    container_number: int
    name: str
    description: str | None = None
    status: str
    cpu: int
    memory_mb: int
    disk_gb: int
    ip_address: str | None = None
    image_name: str | None = None


class ContainerStatusDTO(BaseModel):
    container_id: str
    container_number: int
    status: str
    proxmox_status: str
    uptime_seconds: int | None = None
    cpu_usage_percent: float | None = None
    memory_usage_mb: int | None = None


class ContainerOperationDTO(BaseModel):
    container_id: str
    container_number: int
    operation: str
    success: bool
    message: str
    status: str
