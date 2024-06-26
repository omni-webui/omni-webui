from fastapi import APIRouter, Depends, Request
from loguru import logger
from omni_webui.apps.webui.models.memories import Memories, MemoryModel
from omni_webui.config import CHROMA_CLIENT
from omni_webui.utils import get_verified_user
from pydantic import BaseModel

router = APIRouter()


@router.get("/ef")
async def get_embeddings(request: Request):
    return {"result": request.app.state.EMBEDDING_FUNCTION("hello world")}


############################
# GetMemories
############################


@router.get("/", response_model=list[MemoryModel])
async def get_memories(user=Depends(get_verified_user)):
    return Memories.get_memories_by_user_id(user.id)


############################
# AddMemory
############################


class AddMemoryForm(BaseModel):
    content: str


@router.post("/add", response_model=MemoryModel)
async def add_memory(
    request: Request, form_data: AddMemoryForm, user=Depends(get_verified_user)
):
    memory = Memories.insert_new_memory(user.id, form_data.content)
    assert memory is not None
    memory_embedding = request.app.state.EMBEDDING_FUNCTION(memory.content)

    collection = CHROMA_CLIENT.get_or_create_collection(name=f"user-memory-{user.id}")
    collection.upsert(
        documents=[memory.content],
        ids=[memory.id],
        embeddings=[memory_embedding],
        metadatas=[{"created_at": memory.created_at}],
    )

    return memory


############################
# QueryMemory
############################


class QueryMemoryForm(BaseModel):
    content: str


@router.post("/query")
async def query_memory(
    request: Request, form_data: QueryMemoryForm, user=Depends(get_verified_user)
):
    query_embedding = request.app.state.EMBEDDING_FUNCTION(form_data.content)
    collection = CHROMA_CLIENT.get_or_create_collection(name=f"user-memory-{user.id}")

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=1,  # how many results to return
    )

    return results


############################
# ResetMemoryFromVectorDB
############################
@router.get("/reset", response_model=bool)
async def reset_memory_from_vector_db(
    request: Request, user=Depends(get_verified_user)
):
    CHROMA_CLIENT.delete_collection(f"user-memory-{user.id}")
    collection = CHROMA_CLIENT.get_or_create_collection(name=f"user-memory-{user.id}")

    memories = Memories.get_memories_by_user_id(user.id)
    for memory in memories:
        memory_embedding = request.app.state.EMBEDDING_FUNCTION(memory.content)
        collection.upsert(
            documents=[memory.content],
            ids=[memory.id],
            embeddings=[memory_embedding],
        )
    return True


############################
# DeleteMemoriesByUserId
############################


@router.delete("/user", response_model=bool)
async def delete_memory_by_user_id(user=Depends(get_verified_user)):
    result = Memories.delete_memories_by_user_id(user.id)

    if result:
        try:
            CHROMA_CLIENT.delete_collection(f"user-memory-{user.id}")
        except Exception as e:
            logger.error(e)
        return True

    return False


############################
# DeleteMemoryById
############################


@router.delete("/{memory_id}", response_model=bool)
async def delete_memory_by_id(memory_id: str, user=Depends(get_verified_user)):
    result = Memories.delete_memory_by_id_and_user_id(memory_id, user.id)

    if result:
        collection = CHROMA_CLIENT.get_or_create_collection(
            name=f"user-memory-{user.id}"
        )
        collection.delete(ids=[memory_id])
        return True

    return False
