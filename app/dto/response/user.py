from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuthenticatedUserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
