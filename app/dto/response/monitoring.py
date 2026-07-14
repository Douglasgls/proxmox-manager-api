from pydantic import BaseModel, Field

# TODO:Lembrar de mover esse DTO para a pasta DTOs
class HostInventoryDTO(BaseModel):
    hostname: str
    proxmox_version: str | None = None
    kernel_version: str | None = None
    architecture: str | None = None
    cpu_model: str | None = None
    cpu_cores: int | None = None
    cpu_threads: int | None = None
    memory_total_bytes: int | None = None
    swap_total_bytes: int | None = None
    containers_total: int
    containers_running: int
    containers_stopped: int
    containers_locked: int
    containers_suspended: int
    iso_count: int
    template_count: int


class ContainerInventoryDTO(BaseModel):
    container_id: int
    name: str
    status: str
    locked: bool
    lock: str | None = None
    cpu_cores: int | None = None
    memory_total_bytes: int | None = None
    disk_total_bytes: int | None = None


class ContainerInventorySummaryDTO(BaseModel):
    containers: list[ContainerInventoryDTO] = Field(default_factory=list)
    total: int
    running: int
    stopped: int
    locked: int
    suspended: int


class StorageInventoryDTO(BaseModel):
    name: str
    storage_type: str | None = None
    active: bool
    enabled: bool
    shared: bool
    content_types: list[str] = Field(default_factory=list)
    total_bytes: int | None = None


class NetworkInterfaceDTO(BaseModel):
    name: str
    interface_type: str | None = None
    active: bool
    address: str | None = None
    netmask: str | None = None
    gateway: str | None = None


class NetworkInventoryDTO(BaseModel):
    bridges: list[NetworkInterfaceDTO] = Field(default_factory=list)
    interfaces: list[NetworkInterfaceDTO] = Field(default_factory=list)


class HostMetricsDTO(BaseModel):
    cpu_usage_percent: float | None = None
    memory_used_bytes: int | None = None
    memory_free_bytes: int | None = None
    swap_used_bytes: int | None = None
    swap_free_bytes: int | None = None
    disk_used_bytes: int | None = None
    disk_free_bytes: int | None = None
    rx_bytes: int | None = None
    tx_bytes: int | None = None
    load_average: list[float] = Field(default_factory=list)
    uptime_seconds: int | None = None


class ContainerMetricsDTO(BaseModel):
    container_id: int
    cpu_usage_percent: float | None = None
    memory_used_bytes: int | None = None
    memory_usage_percent: float | None = None
    swap_used_bytes: int | None = None
    disk_used_bytes: int | None = None
    disk_usage_percent: float | None = None
    rx_bytes: int | None = None
    tx_bytes: int | None = None
    io_read_bytes: int | None = None
    io_write_bytes: int | None = None
    status: str
    uptime_seconds: int | None = None


class StorageMetricsDTO(BaseModel):
    name: str
    used_bytes: int | None = None
    free_bytes: int | None = None
    usage_percent: float | None = None
