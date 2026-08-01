from app.core.config import (
    GoogleSettings,
    KnowledgeSupabaseSettings,
    MetaSettings,
    ReportingSupabaseSettings,
    Settings,
)


def test_exact_backend_environment_names_are_loaded_and_redacted(monkeypatch) -> None:
    monkeypatch.setenv("REPORTING_SUPABASE_URL", "https://reporting.invalid")
    monkeypatch.setenv("REPORTING_SUPABASE_SERVICE_ROLE_KEY", "r" * 32)
    settings = ReportingSupabaseSettings(_env_file=None)

    assert settings.configured is True
    assert settings.model_dump() == {}
    assert "reporting.invalid" not in repr(settings)
    assert "r" * 32 not in repr(settings)


def test_legacy_reporting_names_and_placeholders_are_not_accepted(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://legacy.invalid")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "s" * 32)
    settings = ReportingSupabaseSettings(_env_file=None)
    placeholder = ReportingSupabaseSettings(
        url="https://your-reporting-project.supabase.co",
        service_role_key="replace-with-reporting-service-role-key",
        _env_file=None,
    )

    assert settings.configured is False
    assert placeholder.configured is False


def test_knowledge_database_uri_is_not_mistaken_for_postgrest_url() -> None:
    settings = KnowledgeSupabaseSettings(
        url="postgresql://synthetic.invalid/database",
        service_role_key="k" * 32,
        _env_file=None,
    )

    assert settings.configured is False


def test_connector_placeholders_are_not_treated_as_credentials() -> None:
    meta = MetaSettings(
        access_token="replace-with-meta-access-token",
        silpa_access_token="replace-with-silpa-access-token",
        superk_access_token="replace-with-superk-access-token",
        superk_ads_access_token="replace-with-superk-ads-access-token",
        franchise_ads_access_token="replace-with-franchise-ads-access-token",
        superk_page_access_token="replace-with-superk-access-token",
        franchise_page_access_token="replace-with-franchise-access-token",
        _env_file=None,
    )
    google = GoogleSettings(
        oauth_client_id="your-google-client-id",
        oauth_client_secret="change-me",
        oauth_redirect_uri="placeholder",
        _env_file=None,
    )
    settings = Settings(token_encryption_key="replace-with-32-byte-key", _env_file=None)

    assert meta.access_token is None
    assert meta.silpa_access_token is None
    assert meta.superk_access_token is None
    assert meta.superk_ads_access_token is None
    assert meta.franchise_ads_access_token is None
    assert meta.superk_page_access_token is None
    assert meta.franchise_page_access_token is None
    assert google.oauth_client_id is None
    assert google.oauth_client_secret is None
    assert google.oauth_redirect_uri is None
    assert settings.token_encryption_key is None


def test_silpa_and_superk_use_their_exact_client_scoped_tokens(monkeypatch) -> None:
    monkeypatch.setenv("META_ACCESS_TOKEN", "default-meta-token")
    monkeypatch.setenv("SILPA_ACCESS_TOKEN", "silpa-exact-token")
    monkeypatch.setenv("SUPERK_ACCESS_TOKEN", "superk-exact-token")
    monkeypatch.setenv("SUPERK_META_ACCESS_TOKEN", "superk-ads-token")
    monkeypatch.setenv("FRANCHISE_META_ACCESS_TOKEN", "franchise-ads-token")
    monkeypatch.setenv("SUPERK_PAGE_ACCESS_TOKEN", "superk-meta-token")
    monkeypatch.setenv("FRANCHISE_PAGE_ACCESS_TOKEN", "franchise-meta-token")
    settings = MetaSettings(_env_file=None)

    silpa_token = settings.access_token_for_client("silpa")
    superk_token = settings.access_token_for_client("SuperK")
    franchise_token = settings.access_token_for_client("franchise")
    default_token = settings.access_token_for_client("another-client")

    assert silpa_token is not None
    assert silpa_token.get_secret_value() == "silpa-exact-token"
    assert superk_token is not None
    assert superk_token.get_secret_value() == "superk-exact-token"
    assert franchise_token is not None
    assert franchise_token.get_secret_value() == "franchise-ads-token"
    assert default_token is not None
    assert default_token.get_secret_value() == "default-meta-token"
    assert "superk-meta-token" not in repr(settings)
    assert "franchise-meta-token" not in repr(settings)
    assert "superk-ads-token" not in repr(settings)
    assert "franchise-ads-token" not in repr(settings)
    assert "silpa-exact-token" not in repr(settings)
    assert "superk-exact-token" not in repr(settings)
