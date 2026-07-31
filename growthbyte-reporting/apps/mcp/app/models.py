from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    service: Literal["mcp"] = "mcp"
    status: Literal["ok", "ready"]
    version: str
