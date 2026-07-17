from pydantic import BaseModel
from datetime import datetime


class AccessTokenCreateResponseDTO(BaseModel):
    token: str
    expires_at: datetime
    created_at: datetime


class AccessTokenMetadataDTO(BaseModel):
    id: str
    created_at: datetime
    expires_at: datetime
    active: bool
    last_used_at: datetime | None


class AccessTokenRevokeResponseDTO(BaseModel):
    message: str
