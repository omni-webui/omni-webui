from typing import cast

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from openai import AsyncStream
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    CompletionCreateParams,
)
from pydantic import RootModel

from ....models.config import ConfigDepends
from ....models.user import CurrentUserDepends

router = APIRouter()


@router.get("/chat/completions")
async def create_chat_completion(
    root_params: RootModel[CompletionCreateParams],
    user: CurrentUserDepends,
    config: ConfigDepends,
):
    client = config.openai.clients[0]
    params = root_params.root
    stream = params.get("stream") or False
    response = await client.chat.completions.create(**params)  # type: ignore
    if stream:
        chunks = cast(AsyncStream[ChatCompletionChunk], response)

        async def _stream():
            async for chunk in chunks:
                yield f"data: {chunk.model_dump_json()}\n\n"

            yield "data: [DONE]\n\n"

        return StreamingResponse(_stream())
    return cast(ChatCompletion, response)
