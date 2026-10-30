from pydantic import BaseModel, Field
from datetime import datetime


class AccessTokenCreateRequestDTO(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    expires_in_days: int | None = Field(default=None, ge=1)
    expires_in_hours: int | None = Field(default=None, ge=1)
    expires_in_minutes: int | None = Field(default=None, ge=1)


class AccessTokenCreateResponseDTO(BaseModel):
    token: str
    expires_at: datetime
    created_at: datetime
    description: str | None = None


class AccessTokenMetadataDTO(BaseModel):
    id: str
    created_at: datetime
    expires_at: datetime
    active: bool
    last_used_at: datetime | None
    description: str | None = None


class AccessTokenRevokeResponseDTO(BaseModel):
    message: str


class ClientConnectionDTO(BaseModel):
    id: str
    hostname: str | None = None
    tailscale_ip: str | None = None
    online: bool = True
    status: str = "ACTIVE"
    last_seen: datetime | None = None
    created_at: datetime | None = None
