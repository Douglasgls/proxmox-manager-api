from pydantic import BaseModel


class TailscaleSetupResponse(BaseModel):
    job_id: str
