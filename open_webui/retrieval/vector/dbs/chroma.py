"""Chroma client to interact with the Chroma database."""

from typing import Sequence

import chromadb
from chromadb.config import Settings
from chromadb.utils.batch_utils import create_batches
from loguru import logger

from open_webui.config import (
    CHROMA_CLIENT_AUTH_CREDENTIALS,
    CHROMA_CLIENT_AUTH_PROVIDER,
    CHROMA_DATA_PATH,
    CHROMA_DATABASE,
    CHROMA_HTTP_HEADERS,
    CHROMA_HTTP_HOST,
    CHROMA_HTTP_PORT,
    CHROMA_HTTP_SSL,
    CHROMA_TENANT,
)
from open_webui.retrieval.vector.main import GetResult, SearchResult, VectorItem


class ChromaClient:
    """Chroma client to interact with the Chroma database."""

    def __init__(self):  # noqa: D107
        settings = Settings(
            allow_reset=True,
            anonymized_telemetry=False,
        )
        if CHROMA_CLIENT_AUTH_PROVIDER is not None:
            settings.chroma_client_auth_provider = CHROMA_CLIENT_AUTH_PROVIDER
        if CHROMA_CLIENT_AUTH_CREDENTIALS is not None:
            settings.chroma_client_auth_credentials = CHROMA_CLIENT_AUTH_CREDENTIALS

        if CHROMA_HTTP_HOST != "":
            self.client = chromadb.HttpClient(
                host=CHROMA_HTTP_HOST,
                port=CHROMA_HTTP_PORT,
                headers=CHROMA_HTTP_HEADERS,
                ssl=CHROMA_HTTP_SSL,
                tenant=CHROMA_TENANT,
                database=CHROMA_DATABASE,
                settings=settings,
            )
        else:
            self.client = chromadb.PersistentClient(
                path=CHROMA_DATA_PATH,
                settings=settings,
                tenant=CHROMA_TENANT,
                database=CHROMA_DATABASE,
            )

    def has_collection(self, collection_name: str) -> bool:
        """Check if the collection exists based on the collection name."""
        collections = self.client.list_collections()
        return collection_name in [collection.name for collection in collections]

    def delete_collection(self, collection_name: str):
        """Delete the collection based on the collection name."""
        return self.client.delete_collection(name=collection_name)

    def search(
        self,
        collection_name: str,
        vectors: list[Sequence[float] | Sequence[int]],
        limit: int,
    ) -> SearchResult | None:
        """Search for the nearest neighbor items based on the vectors and return 'limit' number of results."""
        try:
            collection = self.client.get_collection(name=collection_name)
            if collection:
                result = collection.query(query_embeddings=vectors, n_results=limit)

                return SearchResult(
                    **{
                        "ids": result["ids"],
                        "distances": result["distances"],
                        "documents": result["documents"],
                        "metadatas": result["metadatas"],
                    }
                )
            return None
        except Exception:
            return None

    def query(
        self, collection_name: str, filter: dict, limit: int | None = None
    ) -> GetResult | None:
        """Query the items from the collection based on the filter."""
        try:
            collection = self.client.get_collection(name=collection_name)
            if collection:
                result = collection.get(
                    where=filter,
                    limit=limit,
                )

                return GetResult(
                    **{
                        "ids": [result["ids"]],
                        "documents": [result["documents"]],
                        "metadatas": [result["metadatas"]],
                    }
                )
            return None
        except Exception as e:
            logger.exception(e)
            return None

    def get(self, collection_name: str) -> GetResult | None:
        """Get all the items in the collection."""
        collection = self.client.get_collection(name=collection_name)
        if collection:
            result = collection.get()
            return GetResult(
                **{
                    "ids": [result["ids"]],
                    "documents": [result["documents"]],
                    "metadatas": [result["metadatas"]],
                }
            )
        return None

    def insert(self, collection_name: str, items: list[VectorItem]):
        """Insert the items into the collection, if the collection does not exist, it will be created."""
        collection = self.client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )

        ids = [item.id for item in items]
        documents = [item.text for item in items]
        embeddings = [item.vector for item in items]
        metadatas = [item.metadata for item in items]

        for batch in create_batches(
            api=self.client,
            documents=documents,
            embeddings=embeddings,  # type: ignore
            ids=ids,
            metadatas=metadatas,
        ):
            collection.add(*batch)

    def upsert(self, collection_name: str, items: list[VectorItem]):
        """Update the items in the collection, if the items are not present, insert them. If the collection does not exist, it will be created."""
        collection = self.client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )

        ids = [item.id for item in items]
        documents = [item.text for item in items]
        embeddings = [item.vector for item in items]
        metadatas = [item.metadata for item in items]

        collection.upsert(
            ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas
        )

    def delete(
        self,
        collection_name: str,
        ids: list[str] | None = None,
        filter: dict | None = None,
    ):
        """Delete the items from the collection based on the ids."""
        collection = self.client.get_collection(name=collection_name)
        if collection:
            if ids:
                collection.delete(ids=ids)
            elif filter:
                collection.delete(where=filter)

    def reset(self):
        """Reset the database. This will delete all collections and item entries."""
        return self.client.reset()
