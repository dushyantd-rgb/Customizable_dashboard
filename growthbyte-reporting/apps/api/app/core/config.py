import base64
import binascii
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


_PLACEHOLDER_MARKERS = (
    "change-me",
    "placeholder",
    "replace-with",
    "sample",
    "your-",
    "your_",
)


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return not normalized or any(marker in normalized for marker in _PLACEHOLDER_MARKERS)


def _normalize_optional_secret(value: object) -> object | None:
    if value is None:
        return None
    raw_value = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
    return None if _is_placeholder(raw_value) else value


class SupabaseConnectionSettings(BaseSettings):
    """Secret-safe settings for one backend-only Supabase connection."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    url: str | None = Field(default=None, exclude=True, repr=False)
    service_role_key: SecretStr | None = Field(default=None, exclude=True, repr=False)

    @field_validator("url", mode="before")
    @classmethod
    def normalize_url(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if _is_placeholder(normalized):
            return None
        parsed = urlsplit(normalized)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None
        return normalized.rstrip("/")

    @field_validator("service_role_key", mode="before")
    @classmethod
    def normalize_service_role_key(cls, value: object) -> object | None:
        if value is None:
            return None
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        if _is_placeholder(raw_value) or len(raw_value.strip()) < 16:
            return None
        return value

    @property
    def configured(self) -> bool:
        return self.url is not None and self.service_role_key is not None


class ReportingSupabaseSettings(SupabaseConnectionSettings):
    url: str | None = Field(
        default=None,
        validation_alias="REPORTING_SUPABASE_URL",
        exclude=True,
        repr=False,
    )
    service_role_key: SecretStr | None = Field(
        default=None,
        validation_alias="REPORTING_SUPABASE_SERVICE_ROLE_KEY",
        exclude=True,
        repr=False,
    )


class KnowledgeSupabaseSettings(SupabaseConnectionSettings):
    url: str | None = Field(
        default=None,
        validation_alias="SUPABASE_KNOWLEDGE_BASE_URL",
        exclude=True,
        repr=False,
    )
    service_role_key: SecretStr | None = Field(
        default=None,
        validation_alias="SUPABASE_KNOWLEDGE_BASE_SERVICE_ROLE_KEY",
        exclude=True,
        repr=False,
    )


class MetaSettings(BaseSettings):
    """Settings for Meta (Facebook/Instagram) API integration."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    access_token: SecretStr | None = Field(
        default=None,
        validation_alias="META_ACCESS_TOKEN",
        exclude=True,
        repr=False,
    )
    graph_api_version: str = Field(
        default="v19.0",
        validation_alias="META_GRAPH_API_VERSION",
        pattern=r"^v\d+\.\d+$",
    )

    @field_validator("access_token", mode="before")
    @classmethod
    def normalize_access_token(cls, value: object) -> object | None:
        return _normalize_optional_secret(value)


class GoogleSettings(BaseSettings):
    """Settings for Google OAuth integration."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    oauth_client_id: SecretStr | None = Field(
        default=None,
        validation_alias="GOOGLE_OAUTH_CLIENT_ID",
        exclude=True,
        repr=False,
    )
    oauth_client_secret: SecretStr | None = Field(
        default=None,
        validation_alias="GOOGLE_OAUTH_CLIENT_SECRET",
        exclude=True,
        repr=False,
    )
    oauth_redirect_uri: str | None = Field(
        default=None,
        validation_alias="GOOGLE_OAUTH_REDIRECT_URI",
    )

    @field_validator("oauth_client_id", "oauth_client_secret", mode="before")
    @classmethod
    def normalize_oauth_secret(cls, value: object) -> object | None:
        return _normalize_optional_secret(value)

    @field_validator("oauth_redirect_uri", mode="before")
    @classmethod
    def normalize_redirect_uri(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if _is_placeholder(normalized):
            return None
        parsed = urlsplit(normalized)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None
        return normalized


class Settings(BaseSettings):
    """Application settings with isolated backend-only credential groups."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "growthbyte-reporting"
    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    web_url: str = Field(default="http://localhost:3000", min_length=1)
    reporting_supabase: ReportingSupabaseSettings = Field(default_factory=ReportingSupabaseSettings)
    knowledge_supabase: KnowledgeSupabaseSettings = Field(default_factory=KnowledgeSupabaseSettings)
    token_encryption_key: SecretStr | None = Field(
        default=None,
        validation_alias="TOKEN_ENCRYPTION_KEY",
        exclude=True,
        repr=False,
    )
    meta: MetaSettings = Field(default_factory=MetaSettings)
    google: GoogleSettings = Field(default_factory=GoogleSettings)

    @field_validator("token_encryption_key", mode="before")
    @classmethod
    def normalize_encryption_key(cls, value: object) -> object | None:
        normalized = _normalize_optional_secret(value)
        if normalized is None:
            return None
        raw_value = (
            normalized.get_secret_value() if isinstance(normalized, SecretStr) else str(normalized)
        )
        try:
            decoded = base64.b64decode(raw_value, validate=True)
        except (binascii.Error, ValueError):
            return None
        return normalized if len(decoded) == 32 else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
