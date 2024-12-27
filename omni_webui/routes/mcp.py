from fastapi import APIRouter
from mcp.client.stdio import StdioServerParameters
from pydantic import BaseModel

from ..config import Settings
from ..deps import SettingsDepends

router = APIRouter()


class ServerParams(BaseModel):
    mcpServers: dict[str, StdioServerParameters]


@router.post(
    "/servers",
    response_model=Settings,
    response_model_include={"mcpServers"},
    response_model_exclude_none=True,
)
async def create_server(server: ServerParams, settings: SettingsDepends):
    settings.mcpServers |= server.mcpServers
    settings.save()
    return settings


@router.get(
    "/servers",
    response_model=Settings,
    response_model_include={"mcpServers"},
    response_model_exclude_none=True,
)
async def retrieve_servers(settings: SettingsDepends):
    return settings
