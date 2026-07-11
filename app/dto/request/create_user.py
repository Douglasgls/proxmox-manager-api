from pydantic import BaseModel, Field


class CreateUserDTO(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=72)
    email: str = Field(min_length=1, max_length=120)
    role: str = "admin"
