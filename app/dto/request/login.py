from pydantic import BaseModel, Field


class LoginRequestDTO(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1, max_length=72)
