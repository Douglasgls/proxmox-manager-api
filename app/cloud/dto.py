from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CloudMessage(BaseModel):
    """Mensagem recebida da Cloud."""

    request_id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class CloudResponse(BaseModel):
    """Resposta enviada para a Cloud."""

    request_id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class CloudErrorDetail(BaseModel):
    code: str
    message: str


class CloudError(BaseModel):
    """Mensagem de erro enviada para a Cloud."""

    request_id: str
    success: bool = False
    error: CloudErrorDetail


class AgentRegistrationDTO(BaseModel):
    """DTO para registrar o Environment Token na API Local."""

    model_config = ConfigDict(extra="forbid")

    environment_token: str = Field(min_length=1)
