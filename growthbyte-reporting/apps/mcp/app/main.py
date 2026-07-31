from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.models import HealthResponse
from app.tools import register_tools

settings = get_settings()

mcp_server = FastMCP(
    name="GrowthByte Reporting MCP",
    instructions="Phase 1 transport foundation; no tools are registered.",
    json_response=True,
    stateless_http=True,
    streamable_http_path=settings.mcp_path,
)
register_tools(mcp_server)
mcp_transport = mcp_server.streamable_http_app()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(
    title="GrowthByte Reporting MCP",
    version=settings.app_version,
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version)


@app.get("/ready", response_model=HealthResponse, tags=["health"])
async def ready() -> HealthResponse:
    return HealthResponse(status="ready", version=settings.app_version)


app.mount("/", mcp_transport, name="mcp")
