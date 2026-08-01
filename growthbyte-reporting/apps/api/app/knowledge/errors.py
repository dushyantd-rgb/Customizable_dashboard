from app.core.errors import SafeApplicationError


class KnowledgeImportError(SafeApplicationError):
    """Base error with a caller-safe code and message."""

    code = "knowledge_import_error"
    safe_message = "Knowledge import failed"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.safe_message)


class PlaceholderCredentialsError(KnowledgeImportError):
    code = "supabase_not_configured"
    safe_message = "Required Supabase configuration is not available"
    status_code = 503


class InvalidClientIdError(KnowledgeImportError):
    code = "invalid_client_id"
    safe_message = "The target client identifier is invalid"


class InvalidSourceClientIdentifierError(KnowledgeImportError):
    code = "invalid_source_client_identifier"
    safe_message = "The source client identifier is invalid"


class MissingTargetClientError(KnowledgeImportError):
    code = "missing_target_client"
    safe_message = "The target reporting client does not exist"
    status_code = 404


class MissingSourceClientError(KnowledgeImportError):
    code = "missing_source_client"
    safe_message = "The source client does not exist"
    status_code = 404


class DuplicateSourceClientError(KnowledgeImportError):
    code = "duplicate_source_client"
    safe_message = "The source client identifier is not unique"
    status_code = 409


class MissingKnowledgeFieldsError(KnowledgeImportError):
    code = "missing_knowledge_fields"
    safe_message = "Required source knowledge fields are missing"


class SourceVersionUnavailableError(KnowledgeImportError):
    code = "source_version_unavailable"
    safe_message = "A stable source version is unavailable"


class SourceDatabaseUnavailableError(KnowledgeImportError):
    code = "knowledge_database_unavailable"
    safe_message = "The knowledge source is unavailable"
    status_code = 503


class ReportingDatabaseUnavailableError(KnowledgeImportError):
    code = "reporting_database_unavailable"
    safe_message = "The reporting database is unavailable"
    status_code = 503


class MappingValidationError(KnowledgeImportError):
    code = "mapping_validation_failed"
    safe_message = "Knowledge mapping validation failed"


class ApplyConfirmationError(KnowledgeImportError):
    code = "apply_confirmation_failed"
    safe_message = "The explicit target-client confirmation does not match"


class UpsertConflictError(KnowledgeImportError):
    code = "knowledge_upsert_conflict"
    safe_message = "The reporting database rejected the knowledge upsert"
    status_code = 409


class PartialImportError(KnowledgeImportError):
    code = "partial_import_failure"
    safe_message = "The knowledge import did not complete atomically"
