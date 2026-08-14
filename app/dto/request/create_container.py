from typing import Any
from pydantic import BaseModel, Field, field_validator


class ComponentConfigDTO(BaseModel):
    host: str = "0.0.0.0"
    host_port: int | None = None
    container_port: int | None = None
    restart_policy: str = "unless-stopped"

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        if v not in ("0.0.0.0", "127.0.0.1"):
            raise ValueError("O endereço de bind (host) deve ser '0.0.0.0' ou '127.0.0.1'.")
        return v

    @field_validator("host_port", "container_port")
    @classmethod
    def validate_port(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 65535):
            raise ValueError("A porta deve estar entre 1 e 65535.")
        return v

    @field_validator("restart_policy")
    @classmethod
    def validate_restart_policy(cls, v: str) -> str:
        valid_policies = ("no", "unless-stopped", "always")
        if v not in valid_policies:
            raise ValueError(f"A política de restart deve ser uma das seguintes: {', '.join(valid_policies)}.")
        return v


class ComponentRequestItemDTO(BaseModel):
    slug: str
    config: ComponentConfigDTO | dict[str, Any] | None = None


class CreateContainerDTO(BaseModel):

    name: str

    password: str

    cpu: int = 1

    memory_mb: int = 512

    disk_gb: int = 2

    image_name: str | None = None

    storage: str | None = None

    bridge: str = "vmbr0"

    ip_mode: str = "dhcp"

    ip_address: str | None = None

    cidr: int | None = None

    gateway: str | None = None

    firewall: bool = False

    mtu: int | None = None

    vlan: int | None = None

    mac_address: str | None = None

    components: list[str | ComponentRequestItemDTO | dict[str, Any]] = Field(
        default_factory=list
    )


class InstallContainerComponentsDTO(BaseModel):
    components: list[str | ComponentRequestItemDTO | dict[str, Any]] = Field(
        default_factory=list
    )
