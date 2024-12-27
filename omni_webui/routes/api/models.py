from typing import cast

from aiocache import cached
from httpx import AsyncClient
from ollama._types import ListResponse
from openai.pagination import AsyncPage
from openai.types.model import Model

from ...config import ClientConfig
from ...models._utils import now_timestamp
from ...models.config import ConfigDepends
from ...models.user import UserDepends


def model_hash(self: Model):
    return hash((self.id, self.created, self.owned_by))


OLLAMA_EMBEDDING_MODELS = (
    "nomic-embed-text",
    "mxbai-embed-large",
    "snowflake-arctic-embed",
    "snowflake-arctic-embed2",
    "granite-embedding",
)


def prefix(api_config: ClientConfig | None) -> str:
    prefix = None if api_config is None else api_config.prefix_id
    return f"{prefix}." if prefix else ""


@cached(ttl=3)
async def list_models(config: ConfigDepends, user: UserDepends) -> AsyncPage[Model]:
    openai_models: list[Model] = []
    if config.openai.enable:
        for client in config.openai.clients:
            api_config = config.openai.api_configs.get(str(client.base_url))
            async for model in await client.models.list():
                model.name = model.id  # type: ignore
                model.id = f"{prefix(api_config)}{model.id}"
                model.__hash__ = model_hash  # type: ignore
                if model not in openai_models:
                    openai_models.append(model)
    ollama_models: list[Model] = []
    if config.ollama.enable:
        for client in config.ollama.clients:
            models = (await client.list())["models"]
            api_config = config.ollama.api_configs.get(
                str(cast(AsyncClient, client._client)._base_url)
            )
            for ollama_model in models:
                ollama_model = cast(ListResponse.Model, ollama_model)
                if ollama_model.model is None or ollama_model.modified_at is None:
                    continue
                name, *_ = ollama_model.model.split(":")
                if name in OLLAMA_EMBEDDING_MODELS:
                    continue
                model = Model(
                    id=f"{prefix(api_config)}{ollama_model.model}",
                    created=int(ollama_model.modified_at.timestamp()),
                    owned_by="ollama",
                    object="model",
                    name=ollama_model.model,  # type: ignore
                    ollama=ollama_model,  # type: ignore
                )
                model.__hash__ = model_hash  # type: ignore
                if model not in ollama_models:
                    ollama_models.append(model)
    arena_models: list[Model] = [
        Model(
            id=arena_model.id,
            created=now_timestamp(),
            owned_by="arena",
            object="model",
            name=arena_model.name,  # type: ignore
            info={"meta": arena_model.meta},  # type: ignore
            arena=True,  # type: ignore
        )
        for arena_model in config.evaluation.arena.models
    ]
    return AsyncPage(
        data=arena_models + openai_models + ollama_models,
        object="list",
    )
