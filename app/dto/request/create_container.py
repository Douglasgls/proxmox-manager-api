from pydantic import BaseModel


class CreateContainerDTO(BaseModel):

    name: str

    password: str

    cpu: int = 1

    memory_mb: int = 512

    disk_gb: int = 2

    image_name: str | None = None

    bridge: str = "vmbr0"

    ip_mode: str = "dhcp"

    ip_address: str | None = None

    cidr: int | None = None

    gateway: str | None = None

    firewall: bool = False

    mtu: int | None = None

    vlan: int | None = None

    mac_address: str | None = None

    components: list[str] = []
