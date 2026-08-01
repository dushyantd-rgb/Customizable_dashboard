"""Secret-safe errors for the client-locked SuperK reporting endpoint."""

from app.core.errors import SafeApplicationError


class SuperKConfigurationError(SafeApplicationError):
    code = "superk_not_configured"
    safe_message = "The SuperK Franchise report is not configured"
    status_code = 503


class SuperKClientNotFoundError(SafeApplicationError):
    code = "superk_client_not_found"
    safe_message = "The SuperK Franchise reporting client does not exist"
    status_code = 404


class SuperKPersistenceError(SafeApplicationError):
    code = "superk_report_persistence_failed"
    safe_message = "The SuperK Franchise report could not be stored"
    status_code = 409
