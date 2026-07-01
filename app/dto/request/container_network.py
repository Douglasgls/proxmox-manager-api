from pydantic import BaseModel


class UpdateContainerNetworkDTO(BaseModel):
    bridge: str | None = None
    ip_mode: str | None = None
    ip_address: str | None = None
    cidr: int | None = None
    gateway: str | None = None
    firewall: bool | None = None
    mtu: int | None = None
    vlan: int | None = None
    mac_address: str | None = None
