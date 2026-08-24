from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, AliasChoices



class CloudMessage(BaseModel):
    """Mensagem recebida da Cloud."""

    model_config = ConfigDict(extra="ignore")

    request_id: str | None = None
    event_id: str | None = None
    occurred_at: str | None = None
    type: str
    version: int | None = 1
    environment_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] | None = None

    def get_event_id(self) -> str | None:
        return self.event_id or self.request_id or self.get_data_dict().get("event_id")

    def get_environment_id(self) -> str | None:
        return self.environment_id or self.payload.get("environment_id") or self.get_data_dict().get("environment_id")

    def get_data_dict(self) -> dict[str, Any]:
        if self.data is not None and isinstance(self.data, dict):
            return self.data
        return self.payload


class NodeSyncEventDataDTO(BaseModel):
    """Dados de um nó Headscale/Tailscale recebidos em evento delta da Cloud."""

    model_config = ConfigDict(extra="ignore")

    action: str | None = None
    node_id: str | None = None
    headscale_node_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("headscale_node_id", "headscale_id")
    )
    machine_id: str | None = None
    hostname: str | None = None
    tailscale_ip: str | None = Field(
        default=None,
        validation_alias=AliasChoices("tailscale_ip", "ip")
    )
    online: bool | None = None
    last_seen: str | None = None
    status: str | None = None
    container_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("api_local_container_id", "container_id", "target_container_id")
    )

    cloud_container_id: str | None = None
    proxmox_container_id: int | None = Field(
        default=None,
        validation_alias=AliasChoices("proxmox_container_id", "vmid", "container_number")
    )



class NodeSyncEventDTO(BaseModel):
    """DTO para validação de evento incremental de sincronização de nó."""

    model_config = ConfigDict(extra="ignore")

    event_id: str | None = None
    request_id: str | None = None
    type: str
    version: int = 1
    environment_id: str | None = None
    occurred_at: str | None = None
    data: NodeSyncEventDataDTO = Field(default_factory=NodeSyncEventDataDTO)



class CloudResponse(BaseModel):
    """Resposta enviada para a Cloud."""

    request_id: str
    origin: str = "agent"
    success: bool = True
    type: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class CloudErrorDetail(BaseModel):
    code: str
    message: str


class CloudError(BaseModel):
    """Mensagem de erro enviada para a Cloud."""

    request_id: str
    origin: str = "agent"
    success: bool = False
    error: CloudErrorDetail


class AgentRegistrationDTO(BaseModel):
    """DTO para registrar o Environment Token na API Local."""

    model_config = ConfigDict(extra="forbid")
    environment_token: str = Field(min_length=1)


class ContainerProvisionPayloadDTO(BaseModel):
    """Payload para provisionamento de container recebido da Cloud."""

    model_config = ConfigDict(extra="ignore")

    request_id: str | None = None
    environment_id: str | None = None
    container_id: str = Field(
        validation_alias=AliasChoices("api_local_container_id", "container_id")
    )
    login_server: str = Field(
        validation_alias=AliasChoices("headscale_url", "login_server")
    )
    auth_key: str = Field(
        validation_alias=AliasChoices("preauth_key", "auth_key")
    )
    hostname: str | None = None
    published_container_id: str | None = None
    container_number: int | None = None
    headscale_user: str | None = None


class PublishedPortDTO(BaseModel):
    port: int
    protocol: str = "tcp"


class PublishedTailscaleNodeSnapshotDTO(BaseModel):
    installed: bool
    service_running: bool
    version: str | None = None
    machine_id: str | None = None
    node_key: str | None = None
    tailscale_ip: str | None = None
    online: bool
    last_sync: Optional[Any] = None  # datetime is handled dynamically or serializable
    hostname: str | None = None
    dns_name: str | None = None
    last_seen: Optional[Any] = None
    advertised_routes: list[str] = Field(default_factory=list)
    ports: list[PublishedPortDTO] = Field(default_factory=list)



class PublishedAccessTokenSnapshotDTO(BaseModel):
    id: str
    token_hash: str
    created_at: Any
    expires_at: Any
    active: bool
    revoked_at: Optional[Any] = None


class PublishedContainerSnapshotDTO(BaseModel):
    api_local_container_id: str
    container_number: int
    name: str
    hostname: str | None = None
    dns_name: str | None = None
    status: str
    tailscale: PublishedTailscaleNodeSnapshotDTO | None = None
    access_tokens: list[PublishedAccessTokenSnapshotDTO] = Field(default_factory=list)
    ports: list[PublishedPortDTO] = Field(default_factory=list)


class EnvironmentDetailsDTO(BaseModel):
    id: str | None = None
    registered_at: Optional[Any] = None


class EnvironmentSnapshotDTO(BaseModel):
    environment: EnvironmentDetailsDTO
    published_containers: list[PublishedContainerSnapshotDTO] = Field(default_factory=list)

