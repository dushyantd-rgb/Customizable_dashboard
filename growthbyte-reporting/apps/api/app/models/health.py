from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    service: Literal["api"] = "api"
    status: Literal["ok"]
    version: str


DependencyState = Literal["configured", "reachable", "unavailable", "not_configured"]


class DependencyReadiness(BaseModel):
    reporting_supabase: DependencyState
    knowledge_supabase: DependencyState


class ReadinessResponse(BaseModel):
    service: Literal["api"] = "api"
    status: DependencyState
    version: str
    dependencies: DependencyReadiness
