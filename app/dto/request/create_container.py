from pydantic import BaseModel


class CreateContainerDTO(BaseModel):

    name: str

    cpu: int = 1

    memory_mb: int = 512

    disk_gb: int = 2

    image_name: str | None = None
