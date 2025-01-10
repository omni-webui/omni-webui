"""Vector API models."""

from typing import Any, Sequence

from pydantic import BaseModel


class VectorItem(BaseModel):
    """Vector item."""

    id: str
    text: str
    vector: Sequence[float] | Sequence[int]
    metadata: Any


class GetResult(BaseModel):
    """Get result."""

    ids: list[list[str]]
    documents: list[list[str]]
    metadatas: list[list[Any]]


class SearchResult(GetResult):
    """Search result."""

    distances: list[list[float | int]] | None
