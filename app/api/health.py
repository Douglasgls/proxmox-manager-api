from fastapi import APIRouter
from fastapi import Depends

from app.core.dependencies import get_proxmox_client
from app.integrations.proxmox import ProxmoxClient


router = APIRouter()


@router.get(
    "/health/proxmox"
)
def proxmox_health(
    proxmox_client: ProxmoxClient = Depends(
        get_proxmox_client
    )
):
    version = proxmox_client.get_version()
    containers = proxmox_client.list_containers()

    return {
        "connected": True,
        "node": proxmox_client.node,
        "containers": len(containers),
        "version": version,
    }
