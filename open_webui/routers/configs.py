"""Configs router."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from open_webui.config import (
    BannerModel,
    ConfigData,
    ConfigDBDep,
    ConfigDep,
    UIConfig,
)
from open_webui.models import SessionDep
from open_webui.utils.auth import get_admin_user, get_verified_user

router = APIRouter()


class ImportConfigForm(BaseModel):
    """Import config form."""

    config: dict


@router.post("/import", response_model=ConfigData, response_model_exclude_none=True)
async def import_config(
    form_data: ImportConfigForm,
    session: SessionDep,
    config_db: ConfigDBDep,
    user=Depends(get_admin_user),
):
    """Import config."""
    config_db.data = ConfigData.model_validate(
        config_db.data.model_dump() | form_data.config
    )
    session.add(config_db)
    await session.commit()
    await session.refresh(config_db)
    return config_db.data


@router.get("/export", response_model=ConfigData, response_model_exclude_none=True)
async def export_config(config: ConfigDep, user=Depends(get_admin_user)):
    """Export config."""
    return config


class ModelsConfigForm(BaseModel):
    """Models config form."""

    DEFAULT_MODELS: str | None
    MODEL_ORDER_LIST: list[str] | None


@router.get("/models", response_model=ModelsConfigForm)
async def get_models_config(config: ConfigDep, user=Depends(get_admin_user)):
    """Get models config."""
    return {
        "DEFAULT_MODELS": config.ui.default_models,
        "MODEL_ORDER_LIST": config.ui.language_model_order_list,
    }


@router.post("/models", response_model=ModelsConfigForm)
async def set_models_config(
    form_data: ModelsConfigForm,
    session: SessionDep,
    config_db: ConfigDBDep,
    user=Depends(get_admin_user),
):
    """Set models config."""
    config_db.data.ui.default_models = form_data.DEFAULT_MODELS
    config_db.data.ui.language_model_order_list = form_data.MODEL_ORDER_LIST or []
    session.add(config_db)
    await session.commit()
    await session.refresh(config_db)
    return {
        "DEFAULT_MODELS": config_db.data.ui.default_models,
        "MODEL_ORDER_LIST": config_db.data.ui.language_model_order_list,
    }


class PromptSuggestion(BaseModel):
    """Prompt suggestion."""

    title: list[str]
    content: str


class SetDefaultSuggestionsForm(BaseModel):
    """Set default suggestions form."""

    suggestions: list[PromptSuggestion]


@router.post("/suggestions", response_model=list[PromptSuggestion])
async def set_default_suggestions(
    suggestions: list[UIConfig.PromptSuggestion],
    session: SessionDep,
    config_db: ConfigDBDep,
    user=Depends(get_admin_user),
):
    """Set default suggestions."""
    config_db.data.ui.prompt_suggestions = suggestions
    session.add(config_db)
    await session.commit()
    await session.refresh(config_db)
    return config_db.data.ui.prompt_suggestions


@router.post("/banners", response_model=list[BannerModel])
async def set_banners(
    banners: list[BannerModel],
    session: SessionDep,
    config_db: ConfigDBDep,
    user=Depends(get_admin_user),
):
    """Set banners."""
    config_db.data.ui.banners = banners
    session.add(config_db)
    await session.commit()
    await session.refresh(config_db)
    return config_db.data.ui.banners


@router.get("/banners", response_model=list[BannerModel])
async def get_banners(
    config: ConfigDep,
    user=Depends(get_verified_user),
):
    """Get banners."""
    return config.ui.banners
