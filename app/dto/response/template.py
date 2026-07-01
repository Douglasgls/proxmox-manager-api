from pydantic import BaseModel
from pydantic import ConfigDict


class OsTemplateResponseDTO(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    name: str
    filename: str
    distribution: str | None = None
    version: str | None = None
    architecture: str | None = None
    description: str | None = None
    storage: str | None = None
    downloaded: bool = False
    size: int | None = None
    source: str | None = None
    volume_id: str | None = None
