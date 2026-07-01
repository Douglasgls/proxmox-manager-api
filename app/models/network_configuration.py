from dataclasses import dataclass
from enum import StrEnum


class NetworkIpMode(StrEnum):
    DHCP = "dhcp"
    STATIC = "static"


@dataclass(frozen=True)
class NetworkConfiguration:
    bridge: str
    ip_mode: NetworkIpMode
    ip_address: str | None = None
    cidr: int | None = None
    gateway: str | None = None
    firewall: bool = False
    mtu: int | None = None
    vlan: int | None = None
    mac_address: str | None = None
    interface_name: str = "eth0"
