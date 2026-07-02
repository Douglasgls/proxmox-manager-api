from pydantic import BaseModel
from datetime import datetime


class ContainerInfo(BaseModel):
    container_id: int
    name: str
    status: str
    cpu: int
    memory_mb: int
    disk_gb: int | None = None
    ip_address: str | None = None
    image_name: str | None = None


class ContainerStatus(BaseModel):
    container_id: int
    status: str
    uptime_seconds: int | None = None
    cpu_usage_percent: float | None = None
    memory_usage_mb: int | None = None
    ip_address: str | None = None


class OperationResult(BaseModel):
    container_id: int
    operation: str
    success: bool
    message: str
    status: str | None = None
    ip_address: str | None = None


class ShellResult(BaseModel):
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    success: bool


class CommandResult(BaseModel):
    success: bool
    command: str
    stdout: str
    stderr: str
    exit_code: int
    duration: float
    executed_at: datetime


class NetworkBridge(BaseModel):
    name: str
    active: bool


class TemplateOperationResult(BaseModel):
    operation: str
    success: bool
    message: str
    storage: str | None = None
    template: str
    task_id: str | None = None
