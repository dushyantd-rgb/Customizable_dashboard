import base64
import binascii
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

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
    silpa_access_token: SecretStr | None = Field(
        default=None,
        validation_alias="SILPA_ACCESS_TOKEN",
        exclude=True,
        repr=False,
    )
    superk_access_token: SecretStr | None = Field(
        default=None,
        validation_alias="SUPERK_ACCESS_TOKEN",
        exclude=True,
        repr=False,
    )
    superk_ads_access_token: SecretStr | None = Field(
        default=None,
        validation_alias="SUPERK_META_ACCESS_TOKEN",
        exclude=True,
        repr=False,
    )
    franchise_ads_access_token: SecretStr | None = Field(
        default=None,
        validation_alias="FRANCHISE_META_ACCESS_TOKEN",
        exclude=True,
        repr=False,
    )
    superk_page_access_token: SecretStr | None = Field(
        default=None,
        validation_alias="SUPERK_PAGE_ACCESS_TOKEN",
        exclude=True,
        repr=False,
    )
    franchise_page_access_token: SecretStr | None = Field(
        default=None,
        validation_alias="FRANCHISE_PAGE_ACCESS_TOKEN",
        exclude=True,
        repr=False,
    )
    graph_api_version: str = Field(
        default="v19.0",
        validation_alias="META_GRAPH_API_VERSION",
        pattern=r"^v\d+\.\d+$",
    )

    @field_validator(
        "access_token",
        "silpa_access_token",
        "superk_access_token",
        "superk_ads_access_token",
        "franchise_ads_access_token",
        "superk_page_access_token",
        "franchise_page_access_token",
        mode="before",
    )
    @classmethod
    def normalize_access_token(cls, value: object) -> object | None:
        return _normalize_optional_secret(value)

    def access_token_for_client(self, client_slug: str) -> SecretStr | None:
        """Return a client-bound token without exposing it to API responses or logs."""
        normalized_slug = client_slug.strip().casefold()
        if normalized_slug == "silpa":
            return self.silpa_access_token
        if normalized_slug == "superk":
            return (
                self.superk_access_token
                or self.superk_ads_access_token
                or self.superk_page_access_token
            )
        if normalized_slug == "franchise":
            return self.franchise_ads_access_token or self.franchise_page_access_token
        return self.access_token


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


class SuperKSettings(BaseSettings):
    """Backend-only identity and source lock for the SuperK Franchise prototype."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    client_id: UUID | None = Field(
        default=None,
        validation_alias="SUPERK_CLIENT_ID",
    )
    franchise_meta_account_id: str | None = Field(
        default=None,
        validation_alias="SUPERK_FRANCHISE_META_ACCOUNT_ID",
    )
    gsc_site_url: str | None = Field(
        default=None,
        validation_alias="SUPERK_GSC_SITE_URL",
    )
    lead_json_path: Path = Field(
        default=PROJECT_ROOT / "superk_purchase_qcom.json",
        validation_alias="SUPERK_LEAD_JSON_PATH",
    )

    @field_validator("client_id", mode="before")
    @classmethod
    def normalize_client_id(cls, value: object) -> object | None:
        if value is None or _is_placeholder(str(value)):
            return None
        try:
            return UUID(str(value).strip())
        except (ValueError, TypeError, AttributeError):
            return None

    @field_validator("franchise_meta_account_id", mode="before")
    @classmethod
    def normalize_meta_account_id(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if _is_placeholder(normalized):
            return None
        if normalized.startswith("act_"):
            normalized = normalized[4:]
        return normalized or None

    @field_validator("gsc_site_url", mode="before")
    @classmethod
    def normalize_gsc_site_url(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if _is_placeholder(normalized):
            return None
        if normalized.startswith("sc-domain:"):
            domain = normalized.removeprefix("sc-domain:").strip().lower()
            return f"sc-domain:{domain}" if domain else None
        parsed = urlsplit(normalized)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None
        return normalized

    @field_validator("lead_json_path", mode="before")
    @classmethod
    def normalize_lead_json_path(cls, value: object) -> Path:
        path = Path(str(value)).expanduser() if value is not None else PROJECT_ROOT
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def configured(self) -> bool:
        return (
            self.client_id is not None
            and self.franchise_meta_account_id is not None
            and self.gsc_site_url is not None
        )


class GLMSettings(BaseSettings):
    """Secret-safe configuration for the Anthropic-compatible GLM gateway."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    base_url: str | None = Field(
        default=None,
        validation_alias="ANTHROPIC_BASE_URL",
        exclude=True,
        repr=False,
    )
    auth_token: SecretStr | None = Field(
        default=None,
        validation_alias="ANTHROPIC_AUTH_TOKEN",
        exclude=True,
        repr=False,
    )
    default_opus_model: str = Field(
        default="claude-opus-5",
        validation_alias="ANTHROPIC_DEFAULT_OPUS_MODEL",
    )
    default_sonnet_model: str = Field(
        default="claude-sonnet-5",
        validation_alias="ANTHROPIC_DEFAULT_SONNET_MODEL",
    )
    default_haiku_model: str = Field(
        default="claude-haiku-4-5",
        validation_alias="ANTHROPIC_DEFAULT_HAIKU_MODEL",
    )
    timeout_seconds: float = Field(default=60.0, ge=10.0, le=300.0)

    @field_validator("base_url", mode="before")
    @classmethod
    def normalize_base_url(cls, value: object) -> str | None:
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

    @field_validator("auth_token", mode="before")
    @classmethod
    def normalize_auth_token(cls, value: object) -> object | None:
        return _normalize_optional_secret(value)

    @property
    def configured(self) -> bool:
        return self.base_url is not None and self.auth_token is not None


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
    superk: SuperKSettings = Field(default_factory=SuperKSettings)
    glm: GLMSettings = Field(default_factory=GLMSettings)

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
