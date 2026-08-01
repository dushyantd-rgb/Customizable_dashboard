"""Google Search Console integration for the SuperK monthly-report prototype."""

from app.integrations.google.search_console.client import GoogleSearchConsoleClient
from app.integrations.google.search_console.repository import SearchConsoleRepository
from app.integrations.google.search_console.service import SearchConsoleService

__all__ = ["GoogleSearchConsoleClient", "SearchConsoleRepository", "SearchConsoleService"]
