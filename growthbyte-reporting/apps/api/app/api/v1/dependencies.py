from typing import Annotated, cast

from fastapi import Depends, Request

from app.data.supabase import ReportingSupabaseClientProtocol
from app.knowledge.errors import PlaceholderCredentialsError


def get_reporting_client(request: Request) -> ReportingSupabaseClientProtocol:
    client = request.app.state.reporting_supabase_client
    if client is None:
        raise PlaceholderCredentialsError
    return cast(ReportingSupabaseClientProtocol, client)


ReportingClientDependency = Annotated[
    ReportingSupabaseClientProtocol,
    Depends(get_reporting_client),
]
