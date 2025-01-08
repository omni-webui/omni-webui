"""Knowledge base API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from pydantic import BaseModel
from sqlmodel import col, select

from open_webui.constants import ERROR_MESSAGES
from open_webui.models import SessionDepends
from open_webui.models.file import File as FileModel
from open_webui.models.knowledge import (
    KnowledgeForm,
    KnowledgeModel,
    KnowledgeResponse,
    Knowledges,
    KnowledgeUserResponse,
)
from open_webui.retrieval.vector.connector import VECTOR_DB_CLIENT
from open_webui.routers.retrieval import (
    BatchProcessFilesForm,
    ProcessFileForm,
    process_file,
    process_files_batch,
)
from open_webui.utils.access_control import has_access, has_permission
from open_webui.utils.auth import get_verified_user

router = APIRouter()


@router.get("/", response_model=list[KnowledgeUserResponse])
async def get_knowledge(session: SessionDepends, user=Depends(get_verified_user)):
    """Get knowledge bases."""
    knowledge_bases = []

    if user.role == "admin":
        knowledge_bases = Knowledges.get_knowledge_bases()
    else:
        knowledge_bases = Knowledges.get_knowledge_bases_by_user_id(user.id, "read")

    # Get files for each knowledge base
    knowledge_with_files = []
    for knowledge_base in knowledge_bases:
        files = []
        if knowledge_base.data:
            file_ids = knowledge_base.data.get("file_ids", [])
            files = list(
                (
                    await session.exec(
                        select(FileModel).filter(col(FileModel.id).in_(file_ids))
                    )
                ).all()
            )

            # Check if all files exist
            if len(files) != len(file_ids):
                missing_files = list(
                    set(knowledge_base.data.get("file_ids", []))
                    - set([file.id for file in files])
                )
                if missing_files:
                    data = knowledge_base.data or {}
                    file_ids = data.get("file_ids", [])

                    for missing_file in missing_files:
                        file_ids.remove(missing_file)

                    data["file_ids"] = file_ids
                    Knowledges.update_knowledge_data_by_id(
                        id=knowledge_base.id, data=data
                    )

                    files = [
                        f.model_dump(include={"id", "meta", "created_at", "updated_at"})
                        for f in (
                            await session.exec(
                                select(FileModel).filter(
                                    col(FileModel.id).in_(file_ids)
                                )
                            )
                        ).all()
                    ]

        knowledge_with_files.append(
            KnowledgeUserResponse(
                **knowledge_base.model_dump(),
                files=files,  # type: ignore
            )
        )

    return knowledge_with_files


@router.get("/list", response_model=list[KnowledgeUserResponse])
async def get_knowledge_list(
    session: SessionDepends,
    user=Depends(get_verified_user),
):
    """Get a list of knowledge bases."""
    knowledge_bases = []

    if user.role == "admin":
        knowledge_bases = Knowledges.get_knowledge_bases()
    else:
        knowledge_bases = Knowledges.get_knowledge_bases_by_user_id(user.id, "write")

    # Get files for each knowledge base
    knowledge_with_files = []
    for knowledge_base in knowledge_bases:
        files = []
        if knowledge_base.data:
            file_ids = knowledge_base.data.get("file_ids", [])
            files = list(
                (
                    await session.exec(
                        select(FileModel).filter(col(FileModel.id).in_(file_ids))
                    )
                ).all()
            )

            # Check if all files exist
            if len(files) != len(knowledge_base.data.get("file_ids", [])):
                missing_files = list(
                    set(knowledge_base.data.get("file_ids", []))
                    - set([file.id for file in files])
                )
                if missing_files:
                    data = knowledge_base.data or {}
                    file_ids = data.get("file_ids", [])

                    for missing_file in missing_files:
                        file_ids.remove(missing_file)

                    data["file_ids"] = file_ids
                    Knowledges.update_knowledge_data_by_id(
                        id=knowledge_base.id, data=data
                    )

                    files = [
                        f.model_dump(include={"id", "meta", "created_at", "updated_at"})
                        for f in (
                            await session.exec(
                                select(FileModel).filter(
                                    col(FileModel.id).in_(file_ids)
                                )
                            )
                        ).all()
                    ]

        knowledge_with_files.append(
            KnowledgeUserResponse(
                **knowledge_base.model_dump(),
                files=files,  # type: ignore
            )
        )
    return knowledge_with_files


############################
# CreateNewKnowledge
############################


@router.post("/create", response_model=Optional[KnowledgeResponse])
async def create_new_knowledge(
    request: Request, form_data: KnowledgeForm, user=Depends(get_verified_user)
):
    """Create a new knowledge base."""
    if user.role != "admin" and not has_permission(
        user.id, "workspace.knowledge", request.app.state.config.USER_PERMISSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    knowledge = Knowledges.insert_new_knowledge(user.id, form_data)

    if knowledge:
        return knowledge
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.FILE_EXISTS,
        )


class KnowledgeFilesResponse(KnowledgeModel):
    """Knowledge files response."""

    files: list[FileModel]


@router.get("/{id}", response_model=Optional[KnowledgeFilesResponse])
async def get_knowledge_by_id(
    id: str,
    session: SessionDepends,
    user=Depends(get_verified_user),
):
    """Get a knowledge base by ID."""
    knowledge = Knowledges.get_knowledge_by_id(id=id)

    if knowledge:
        if (
            user.role == "admin"
            or knowledge.user_id == user.id
            or has_access(user.id, "read", knowledge.access_control)
        ):
            file_ids = knowledge.data.get("file_ids", []) if knowledge.data else []
            statement = select(FileModel).filter(col(FileModel.id).in_(file_ids))
            files = list((await session.exec(statement)).all())

            return KnowledgeFilesResponse(
                **knowledge.model_dump(),
                files=files,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


@router.post("/{id}/update", response_model=Optional[KnowledgeFilesResponse])
async def update_knowledge_by_id(
    id: str,
    form_data: KnowledgeForm,
    session: SessionDepends,
    user=Depends(get_verified_user),
):
    """Update a knowledge base by ID."""
    knowledge = Knowledges.get_knowledge_by_id(id=id)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if knowledge.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    knowledge = Knowledges.update_knowledge_by_id(id=id, form_data=form_data)
    if knowledge:
        file_ids = knowledge.data.get("file_ids", []) if knowledge.data else []
        files = list(
            (
                await session.exec(
                    select(FileModel).filter(col(FileModel.id).in_(file_ids))
                )
            ).all()
        )

        return KnowledgeFilesResponse(
            **knowledge.model_dump(),
            files=files,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ID_TAKEN,
        )


class KnowledgeFileIdForm(BaseModel):
    """Knowledge file ID form."""

    file_id: str


@router.post("/{id}/file/add", response_model=Optional[KnowledgeFilesResponse])
async def add_file_to_knowledge_by_id(
    request: Request,
    id: str,
    form_data: KnowledgeFileIdForm,
    session: SessionDepends,
    user=Depends(get_verified_user),
):
    """Add a file to a knowledge base."""
    knowledge = Knowledges.get_knowledge_by_id(id=id)

    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if knowledge.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    file = await session.get_one(FileModel, id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    if not file.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.FILE_NOT_PROCESSED,
        )

    # Add content to the vector database
    try:
        await process_file(
            request,
            ProcessFileForm(file_id=form_data.file_id, collection_name=id),
            session,
        )
    except Exception as e:
        logger.debug(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if knowledge:
        data = knowledge.data or {}
        file_ids = data.get("file_ids", [])

        if form_data.file_id not in file_ids:
            file_ids.append(form_data.file_id)
            data["file_ids"] = file_ids

            knowledge = Knowledges.update_knowledge_data_by_id(id=id, data=data)

            if knowledge:
                files = list(
                    (
                        await session.exec(
                            select(FileModel).filter(col(FileModel.id).in_(file_ids))
                        )
                    ).all()
                )

                return KnowledgeFilesResponse(
                    **knowledge.model_dump(),
                    files=files,
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.DEFAULT("knowledge"),
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("file_id"),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


@router.post("/{id}/file/update", response_model=Optional[KnowledgeFilesResponse])
async def update_file_from_knowledge_by_id(
    request: Request,
    id: str,
    form_data: KnowledgeFileIdForm,
    session: SessionDepends,
    user=Depends(get_verified_user),
):
    """Update a file in a knowledge base."""
    knowledge = Knowledges.get_knowledge_by_id(id=id)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if knowledge.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    file = await session.get_one(FileModel, id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    # Remove content from the vector database
    VECTOR_DB_CLIENT.delete(
        collection_name=knowledge.id, filter={"file_id": form_data.file_id}
    )

    # Add content to the vector database
    try:
        await process_file(
            request,
            ProcessFileForm(file_id=form_data.file_id, collection_name=id),
            session,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if knowledge:
        data = knowledge.data or {}
        file_ids = data.get("file_ids", [])

        files = list(
            (
                await session.exec(
                    select(FileModel).filter(col(FileModel.id).in_(file_ids))
                )
            ).all()
        )

        return KnowledgeFilesResponse(
            **knowledge.model_dump(),
            files=files,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


@router.post("/{id}/file/remove", response_model=Optional[KnowledgeFilesResponse])
async def remove_file_from_knowledge_by_id(
    id: str,
    form_data: KnowledgeFileIdForm,
    session: SessionDepends,
    user=Depends(get_verified_user),
):
    """Remove a file from a knowledge base."""
    knowledge = Knowledges.get_knowledge_by_id(id=id)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if knowledge.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    file = await session.get_one(FileModel, id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    # Remove content from the vector database
    VECTOR_DB_CLIENT.delete(
        collection_name=knowledge.id, filter={"file_id": form_data.file_id}
    )

    if knowledge:
        data = knowledge.data or {}
        file_ids = data.get("file_ids", [])

        if form_data.file_id in file_ids:
            file_ids.remove(form_data.file_id)
            data["file_ids"] = file_ids

            knowledge = Knowledges.update_knowledge_data_by_id(id=id, data=data)

            if knowledge:
                files = list(
                    (
                        await session.exec(
                            select(FileModel).filter(col(FileModel.id).in_(file_ids))
                        )
                    ).all()
                )

                return KnowledgeFilesResponse(
                    **knowledge.model_dump(),
                    files=files,
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.DEFAULT("knowledge"),
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("file_id"),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


@router.delete("/{id}/delete", response_model=bool)
async def delete_knowledge_by_id(id: str, user=Depends(get_verified_user)):
    """Delete a knowledge base by ID."""
    knowledge = Knowledges.get_knowledge_by_id(id=id)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if knowledge.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    try:
        VECTOR_DB_CLIENT.delete_collection(collection_name=id)
    except Exception as e:
        logger.debug(e)
        pass
    result = Knowledges.delete_knowledge_by_id(id=id)
    return result


@router.post("/{id}/reset", response_model=Optional[KnowledgeResponse])
async def reset_knowledge_by_id(id: str, user=Depends(get_verified_user)):
    """Reset a knowledge base by ID."""
    knowledge = Knowledges.get_knowledge_by_id(id=id)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if knowledge.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    try:
        VECTOR_DB_CLIENT.delete_collection(collection_name=id)
    except Exception as e:
        logger.debug(e)
        pass

    knowledge = Knowledges.update_knowledge_data_by_id(id=id, data={"file_ids": []})

    return knowledge


@router.post("/{id}/files/batch/add", response_model=Optional[KnowledgeFilesResponse])
async def add_files_to_knowledge_batch(
    request: Request,
    id: str,
    form_data: list[KnowledgeFileIdForm],
    session: SessionDepends,
    user=Depends(get_verified_user),
):
    """Add multiple files to a knowledge base."""
    knowledge = Knowledges.get_knowledge_by_id(id=id)
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if knowledge.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    # Get files content
    logger.info(f"files/batch/add - {len(form_data)} files")
    files: list[FileModel] = []
    for form in form_data:
        file = await session.get_one(FileModel, id)
        if not file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File {form.file_id} not found",
            )
        files.append(file)

    # Process files
    try:
        result = await process_files_batch(
            request=request,
            form_data=BatchProcessFilesForm(files=files, collection_name=id),
            session=session,
            user=user,
        )
    except Exception as e:
        logger.error(
            f"add_files_to_knowledge_batch: Exception occurred: {e}", exc_info=True
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Add successful files to knowledge base
    data = knowledge.data or {}
    existing_file_ids = data.get("file_ids", [])

    # Only add files that were successfully processed
    successful_file_ids = [r.file_id for r in result.results if r.status == "completed"]
    for file_id in successful_file_ids:
        if file_id not in existing_file_ids:
            existing_file_ids.append(file_id)

    data["file_ids"] = existing_file_ids
    knowledge = Knowledges.update_knowledge_data_by_id(id=id, data=data)
    assert knowledge is not None

    # If there were any errors, include them in the response
    if result.errors:
        error_details = [f"{err.file_id}: {err.error}" for err in result.errors]
        files = list(
            (
                await session.exec(
                    select(FileModel).filter(col(FileModel.id).in_(existing_file_ids))
                )
            ).all()
        )
        return KnowledgeFilesResponse(
            **knowledge.model_dump(),
            files=files,
            warnings={  # type: ignore
                "message": "Some files failed to process",
                "errors": error_details,
            },
        )

    return KnowledgeFilesResponse(
        **knowledge.model_dump(),
        files=list(
            (
                await session.exec(
                    select(FileModel).filter(col(FileModel.id).in_(existing_file_ids))
                )
            ).all()
        ),
    )
