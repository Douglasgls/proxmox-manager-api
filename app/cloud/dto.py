from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class CloudMessage(BaseModel):
    """Mensagem recebida da Cloud."""

    request_id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


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


class PublishedTailscaleNodeSnapshotDTO(BaseModel):
    installed: bool
    service_running: bool
    version: str | None = None
    machine_id: str | None = None
    node_key: str | None = None
    tailscale_ip: str | None = None
    online: bool
    last_sync: Optional[Any] = None  # datetime is handled dynamically or serializable


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
    status: str
    tailscale: PublishedTailscaleNodeSnapshotDTO | None = None
    access_tokens: list[PublishedAccessTokenSnapshotDTO] = Field(default_factory=list)


class EnvironmentDetailsDTO(BaseModel):
    id: str | None = None
    registered_at: Optional[Any] = None


class EnvironmentSnapshotDTO(BaseModel):
    environment: EnvironmentDetailsDTO
    published_containers: list[PublishedContainerSnapshotDTO] = Field(default_factory=list)

