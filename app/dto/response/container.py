from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, AliasChoices, field_validator


class ContainerComponentResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    category: str
    status: str
    installed_version: str | None = None
    error: str | None = None
    installed_at: datetime | None = None


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
    bridge: str | None = None
    ip_mode: str | None = None
    cidr: int | None = None
    gateway: str | None = None
    firewall: bool | None = False
    mtu: int | None = None
    vlan: int | None = None
    mac_address: str | None = None
    image_name: str | None = None
    components: list[ContainerComponentResponseDTO] = Field(
        default=[],
        validation_alias=AliasChoices("components", "container_components"),
    )

    @field_validator("components", mode="before")
    @classmethod
    def transform_components(cls, v):
        if not v:
            return []
        result = []
        for item in v:
            if hasattr(item, "component") and item.component:
                result.append({
                    "slug": item.component.slug,
                    "name": item.component.name,
                    "category": item.component.category,
                    "status": item.status,
                    "installed_version": item.installed_version,
                    "error": item.error,
                    "installed_at": item.installed_at,
                })
            elif isinstance(item, dict):
                result.append(item)
            elif isinstance(item, str):
                result.append({
                    "slug": item,
                    "name": item.capitalize(),
                    "category": "unknown",
                    "status": "INSTALLED",
                })
        return result



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


class NetworkBridgeDTO(BaseModel):
    name: str
    active: bool
