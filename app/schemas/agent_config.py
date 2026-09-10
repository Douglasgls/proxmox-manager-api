from pydantic import BaseModel
from typing import Optional


class AgentConfigResponse(BaseModel):
    configured: bool
    proxmox_host: Optional[str] = None
    proxmox_user: Optional[str] = None
    proxmox_token_name: Optional[str] = None
    proxmox_node: Optional[str] = None
    default_storage: Optional[str] = None
    default_template: Optional[str] = None


class AgentConfigUpdate(BaseModel):
    proxmox_host: str
    proxmox_user: str
    proxmox_token_name: str
    proxmox_token_value: str
    proxmox_node: str
    default_storage: Optional[str] = None
    default_template: Optional[str] = None


class AgentTestConnection(BaseModel):
    proxmox_host: str
    proxmox_user: str
    proxmox_token_name: str
    proxmox_token_value: str
    proxmox_node: str
