"""Chat API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from pydantic import BaseModel

from open_webui.config import ENABLE_ADMIN_CHAT_ACCESS, ENABLE_ADMIN_EXPORT
from open_webui.constants import ERROR_MESSAGES
from open_webui.models.chats import (
    ChatForm,
    ChatImportForm,
    ChatResponse,
    Chats,
    ChatTitleIdResponse,
)
from open_webui.models.folders import Folders
from open_webui.models.tags import TagModel, Tags
from open_webui.utils.access_control import has_permission
from open_webui.utils.auth import get_admin_user, get_verified_user

router = APIRouter()


@router.get("/", response_model=list[ChatTitleIdResponse])
@router.get("/list", response_model=list[ChatTitleIdResponse])
async def get_session_user_chat_list(
    page: int | None = None, user=Depends(get_verified_user)
):
    """Get chat list by user ID."""
    if page is not None:
        limit = 60
        skip = (page - 1) * limit

        return Chats.get_chat_title_id_list_by_user_id(user.id, skip=skip, limit=limit)
    else:
        return Chats.get_chat_title_id_list_by_user_id(user.id)


@router.delete("/", response_model=bool)
async def delete_all_user_chats(request: Request, user=Depends(get_verified_user)):
    """Delete all chats by user ID."""
    if user.role == "user" and not has_permission(
        user.id, "chat.delete", request.app.state.config.USER_PERMISSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    result = Chats.delete_chats_by_user_id(user.id)
    return result


@router.get("/list/user/{user_id}", response_model=list[ChatTitleIdResponse])
async def get_user_chat_list_by_user_id(
    user_id: str,
    user=Depends(get_admin_user),
    skip: int = 0,
    limit: int = 50,
):
    """Get chat list by user ID."""
    if not ENABLE_ADMIN_CHAT_ACCESS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    return Chats.get_chat_list_by_user_id(
        user_id, include_archived=True, skip=skip, limit=limit
    )


@router.post("/new", response_model=ChatResponse)
async def create_new_chat(form_data: ChatForm, user=Depends(get_verified_user)):
    """Create new chat."""
    chat = Chats.insert_new_chat(user.id, form_data)
    assert chat is not None
    return chat


@router.post("/import", response_model=ChatResponse)
async def import_chat(form_data: ChatImportForm, user=Depends(get_verified_user)):
    """Import chat."""
    chat = Chats.import_chat(user.id, form_data)
    if chat:
        tags = chat.meta.get("tags", [])
        for tag_id in tags:
            tag_id = tag_id.replace(" ", "_").lower()
            tag_name = " ".join([word.capitalize() for word in tag_id.split("_")])
            if (
                tag_id != "none"
                and Tags.get_tag_by_name_and_user_id(tag_name, user.id) is None
            ):
                Tags.insert_new_tag(tag_name, user.id)

    return chat


@router.get("/search", response_model=list[ChatTitleIdResponse])
async def search_user_chats(
    text: str, page: int | None = None, user=Depends(get_verified_user)
):
    """Search chat list by text."""
    if page is None:
        page = 1

    limit = 60
    skip = (page - 1) * limit

    chat_list = [
        ChatTitleIdResponse(**chat.model_dump())
        for chat in Chats.get_chats_by_user_id_and_search_text(
            user.id, text, skip=skip, limit=limit
        )
    ]

    # Delete tag if no chat is found
    words = text.strip().split(" ")
    if page == 1 and len(words) == 1 and words[0].startswith("tag:"):
        tag_id = words[0].replace("tag:", "")
        if len(chat_list) == 0:
            if Tags.get_tag_by_name_and_user_id(tag_id, user.id):
                logger.debug(f"deleting tag: {tag_id}")
                Tags.delete_tag_by_name_and_user_id(tag_id, user.id)

    return chat_list


@router.get("/folder/{folder_id}", response_model=list[ChatResponse])
async def get_chats_by_folder_id(folder_id: str, user=Depends(get_verified_user)):
    """Get chat list by folder ID."""
    folder_ids = [folder_id]
    children_folders = Folders.get_children_folders_by_id_and_user_id(
        folder_id, user.id
    )
    if children_folders:
        folder_ids.extend([folder.id for folder in children_folders])

    return [
        ChatResponse(**chat.model_dump())
        for chat in Chats.get_chats_by_folder_ids_and_user_id(folder_ids, user.id)
    ]


@router.get("/pinned", response_model=list[ChatResponse])
async def get_user_pinned_chats(user=Depends(get_verified_user)):
    """Get pinned chat list by user ID."""
    return [
        ChatResponse(**chat.model_dump())
        for chat in Chats.get_pinned_chats_by_user_id(user.id)
    ]


@router.get("/all", response_model=list[ChatResponse])
async def get_user_chats(user=Depends(get_verified_user)):
    """Get all chat list by user ID."""
    return [
        ChatResponse(**chat.model_dump())
        for chat in Chats.get_chats_by_user_id(user.id)
    ]


@router.get("/all/archived", response_model=list[ChatResponse])
async def get_user_archived_chats(user=Depends(get_verified_user)):
    """Get all archived chat list by user ID."""
    return [
        ChatResponse(**chat.model_dump())
        for chat in Chats.get_archived_chats_by_user_id(user.id)
    ]


@router.get("/all/tags", response_model=list[TagModel])
async def get_all_user_tags(user=Depends(get_verified_user)):
    """Get all tags by user ID."""
    try:
        tags = Tags.get_tags_by_user_id(user.id)
        return tags
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


@router.get("/all/db", response_model=list[ChatResponse])
async def get_all_user_chats_in_db(user=Depends(get_admin_user)):
    """Get all chat list in the database."""
    if not ENABLE_ADMIN_EXPORT:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    return [ChatResponse(**chat.model_dump()) for chat in Chats.get_chats()]


@router.get("/archived", response_model=list[ChatTitleIdResponse])
async def get_archived_session_user_chat_list(
    user=Depends(get_verified_user), skip: int = 0, limit: int = 50
):
    """Get archived chat list by user ID."""
    return Chats.get_archived_chat_list_by_user_id(user.id, skip, limit)


@router.post("/archive/all", response_model=bool)
async def archive_all_chats(user=Depends(get_verified_user)):
    """Archive all chats by user ID."""
    return Chats.archive_all_chats_by_user_id(user.id)


@router.get("/share/{share_id}", response_model=ChatResponse)
async def get_shared_chat_by_id(share_id: str, user=Depends(get_verified_user)):
    """Get shared chat by ID."""
    if user.role == "pending":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if user.role == "user" or (user.role == "admin" and not ENABLE_ADMIN_CHAT_ACCESS):
        chat = Chats.get_chat_by_share_id(share_id)
    elif user.role == "admin" and ENABLE_ADMIN_CHAT_ACCESS:
        chat = Chats.get_chat_by_id(share_id)
    else:
        chat = None
    if chat:
        return chat

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.NOT_FOUND
        )


class TagForm(BaseModel):
    """Request model for tag name."""

    name: str


@router.post("/tags", response_model=list[ChatTitleIdResponse])
async def get_user_chat_list_by_tag_name(
    name: str, skip: int = 0, limit: int = 50, user=Depends(get_verified_user)
):
    """Get chat list by tag name."""
    chats = Chats.get_chat_list_by_user_id_and_tag_name(
        user.id, name, skip=skip, limit=limit
    )
    if len(chats) == 0:
        Tags.delete_tag_by_name_and_user_id(name, user.id)

    return chats


@router.get("/{id}", response_model=ChatResponse)
async def get_chat_by_id(id: str, user=Depends(get_verified_user)):
    """Get chat by ID."""
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    assert chat is not None
    return chat


@router.post("/{id}", response_model=Optional[ChatResponse])
async def update_chat_by_id(
    id: str, form_data: ChatForm, user=Depends(get_verified_user)
):
    """Update chat by ID."""
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    assert chat is not None
    updated_chat = {**chat.chat, **form_data.chat}
    chat = Chats.update_chat_by_id(id, updated_chat)
    assert chat is not None
    return chat


@router.delete("/{id}", response_model=bool)
async def delete_chat_by_id(request: Request, id: str, user=Depends(get_verified_user)):
    """Delete chat by ID."""
    if user.role == "admin":
        chat = Chats.get_chat_by_id(id)
        assert chat is not None
        for tag in chat.meta.get("tags", []):
            if Chats.count_chats_by_tag_name_and_user_id(tag, user.id) == 1:
                Tags.delete_tag_by_name_and_user_id(tag, user.id)

        result = Chats.delete_chat_by_id(id)

        return result
    else:
        if not has_permission(
            user.id, "chat.delete", request.app.state.config.USER_PERMISSIONS
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
            )

        chat = Chats.get_chat_by_id(id)
        assert chat is not None
        for tag in chat.meta.get("tags", []):
            if Chats.count_chats_by_tag_name_and_user_id(tag, user.id) == 1:
                Tags.delete_tag_by_name_and_user_id(tag, user.id)

        result = Chats.delete_chat_by_id_and_user_id(id, user.id)
        return result


@router.get("/{id}/pinned", response_model=Optional[bool])
async def get_pinned_status_by_id(id: str, user=Depends(get_verified_user)):
    """Get pinned status by ID."""
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        return chat.pinned
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.DEFAULT()
        )


@router.post("/{id}/pin", response_model=Optional[ChatResponse])
async def pin_chat_by_id(id: str, user=Depends(get_verified_user)):
    """Pin chat by ID."""
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        chat = Chats.toggle_chat_pinned_by_id(id)
        return chat
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.DEFAULT()
        )


@router.post("/{id}/clone", response_model=ChatResponse)
async def clone_chat_by_id(id: str, user=Depends(get_verified_user)):
    """Clone chat by ID."""
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    assert chat is not None
    updated_chat = {
        **chat.chat,
        "originalChatId": chat.id,
        "branchPointMessageId": chat.chat["history"]["currentId"],
        "title": f"Clone of {chat.title}",
    }

    chat = Chats.insert_new_chat(user.id, ChatForm(**{"chat": updated_chat}))
    assert chat is not None
    return chat


@router.post("/{id}/clone/shared", response_model=ChatResponse)
async def clone_shared_chat_by_id(id: str, user=Depends(get_verified_user)):
    """Clone shared chat by ID."""
    chat = Chats.get_chat_by_share_id(id)
    assert chat is not None
    updated_chat = {
        **chat.chat,
        "originalChatId": chat.id,
        "branchPointMessageId": chat.chat["history"]["currentId"],
        "title": f"Clone of {chat.title}",
    }

    chat = Chats.insert_new_chat(user.id, ChatForm(**{"chat": updated_chat}))
    assert chat is not None
    return chat


@router.post("/{id}/archive", response_model=ChatResponse)
async def archive_chat_by_id(id: str, user=Depends(get_verified_user)):
    """Archive chat by ID."""
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    assert chat is not None
    chat = Chats.toggle_chat_archive_by_id(id)
    assert chat is not None

    # Delete tags if chat is archived
    if chat.archived:
        for tag_id in chat.meta.get("tags", []):
            if Chats.count_chats_by_tag_name_and_user_id(tag_id, user.id) == 0:
                logger.debug(f"deleting tag: {tag_id}")
                Tags.delete_tag_by_name_and_user_id(tag_id, user.id)
    else:
        for tag_id in chat.meta.get("tags", []):
            tag = Tags.get_tag_by_name_and_user_id(tag_id, user.id)
            if tag is None:
                logger.debug(f"inserting tag: {tag_id}")
                tag = Tags.insert_new_tag(tag_id, user.id)
    return chat


@router.post("/{id}/share", response_model=ChatResponse)
async def share_chat_by_id(id: str, user=Depends(get_verified_user)):
    """Share chat by ID."""
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    assert chat is not None
    if chat.share_id:
        shared_chat = Chats.update_shared_chat_by_chat_id(chat.id)
        return shared_chat

    shared_chat = Chats.insert_shared_chat_by_chat_id(chat.id)
    if not shared_chat:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT(),
        )
    return shared_chat


@router.delete("/{id}/share", response_model=Optional[bool])
async def delete_shared_chat_by_id(id: str, user=Depends(get_verified_user)):
    """Delete shared chat by ID."""
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        if not chat.share_id:
            return False

        result = Chats.delete_shared_chat_by_chat_id(id)
        update_result = Chats.update_chat_share_id_by_id(id, None)

        return result and update_result is not None
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )


class ChatFolderIdForm(BaseModel):
    """Request model for updating folder ID of a chat."""

    folder_id: Optional[str] = None


@router.post("/{id}/folder", response_model=Optional[ChatResponse])
async def update_chat_folder_id_by_id(
    id: str, form_data: ChatFolderIdForm, user=Depends(get_verified_user)
):
    """Update folder ID of a chat."""
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        chat = Chats.update_chat_folder_id_by_id_and_user_id(
            id, user.id, form_data.folder_id or ""
        )
        return chat
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.DEFAULT()
        )


@router.get("/{id}/tags", response_model=list[TagModel])
async def get_chat_tags_by_id(id: str, user=Depends(get_verified_user)):
    """Get tags of a chat."""
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if chat:
        tags = chat.meta.get("tags", [])
        return Tags.get_tags_by_ids_and_user_id(tags, user.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.NOT_FOUND
        )


@router.post("/{id}/tags", response_model=list[TagModel])
async def add_tag_by_id_and_tag_name(
    id: str, form_data: TagForm, user=Depends(get_verified_user)
):
    """Add tag to a chat."""
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    assert chat is not None
    tags = chat.meta.get("tags", [])
    tag_id = form_data.name.replace(" ", "_").lower()

    if tag_id == "none":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tag name cannot be 'None'",
        )

    if tag_id not in tags:
        Chats.add_chat_tag_by_id_and_user_id_and_tag_name(id, user.id, form_data.name)

    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    assert chat is not None
    tags = chat.meta.get("tags", [])
    return Tags.get_tags_by_ids_and_user_id(tags, user.id)


@router.delete("/{id}/tags", response_model=list[TagModel])
async def delete_tag_by_id_and_tag_name(
    id: str, form_data: TagForm, user=Depends(get_verified_user)
):
    """Delete tag of a chat."""
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    assert chat is not None
    Chats.delete_tag_by_id_and_user_id_and_tag_name(id, user.id, form_data.name)

    if Chats.count_chats_by_tag_name_and_user_id(form_data.name, user.id) == 0:
        Tags.delete_tag_by_name_and_user_id(form_data.name, user.id)

    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    assert chat is not None
    tags = chat.meta.get("tags", [])
    return Tags.get_tags_by_ids_and_user_id(tags, user.id)


@router.delete("/{id}/tags/all", response_model=Optional[bool])
async def delete_all_tags_by_id(id: str, user=Depends(get_verified_user)):
    """Delete all tags of a chat."""
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    assert chat is not None
    Chats.delete_all_tags_by_id_and_user_id(id, user.id)

    for tag in chat.meta.get("tags", []):
        if Chats.count_chats_by_tag_name_and_user_id(tag, user.id) == 0:
            Tags.delete_tag_by_name_and_user_id(tag, user.id)

    return True
