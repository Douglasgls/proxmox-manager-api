from pydantic import BaseModel, Field


class RefreshRequestDTO(BaseModel):
    refresh_token: str = Field(min_length=1)
