from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    service: Literal["api"] = "api"
    status: Literal["ok", "ready"]
    version: str
