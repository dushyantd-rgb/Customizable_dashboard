class SafeApplicationError(Exception):
    """Application error whose public representation is fixed and secret-safe."""

    code = "application_error"
    safe_message = "The request could not be completed"
    status_code = 400

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.safe_message)


class ClientNotFoundError(SafeApplicationError):
    code = "client_not_found"
    safe_message = "The reporting client does not exist"
    status_code = 404


class KnowledgeRecordNotFoundError(SafeApplicationError):
    code = "knowledge_record_not_found"
    safe_message = "The client knowledge record does not exist"
    status_code = 404


class KpiRecordNotFoundError(SafeApplicationError):
    code = "kpi_record_not_found"
    safe_message = "The client KPI does not exist"
    status_code = 404


class ReportingWriteConflictError(SafeApplicationError):
    code = "reporting_write_conflict"
    safe_message = "The reporting database rejected the requested change"
    status_code = 409


class KpiIntervalError(SafeApplicationError):
    code = "invalid_kpi_interval"
    safe_message = "The KPI effective-date interval is invalid"
    status_code = 422
