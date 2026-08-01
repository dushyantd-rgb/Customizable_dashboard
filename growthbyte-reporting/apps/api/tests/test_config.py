from app.core.config import KnowledgeSupabaseSettings, ReportingSupabaseSettings


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
