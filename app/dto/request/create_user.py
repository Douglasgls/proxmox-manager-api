from pydantic import BaseModel


class CreateUserDTO(BaseModel):
    username: str
    password: str
    role: str = "admin"