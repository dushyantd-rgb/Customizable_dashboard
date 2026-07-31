from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Non-secret settings required by the Phase 1 MCP foundation."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "growthbyte-reporting"
    app_version: str = "0.1.0"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = Field(default=8001, ge=1, le=65535)
    mcp_path: str = "/mcp"


@lru_cache
def get_settings() -> Settings:
    return Settings()
