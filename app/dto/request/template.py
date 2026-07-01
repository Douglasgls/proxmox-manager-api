from pydantic import BaseModel


class DownloadTemplateDTO(BaseModel):
    storage: str
    template: str
