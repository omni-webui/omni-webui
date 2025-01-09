"""Configs router."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from open_webui.config import (
    BannerModel,
    Config,
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
    if config_db is not None:
        config_db.data = ConfigData.model_validate(
            config_db.data.model_dump() | form_data.config
        )
    else:
        config_db = Config.model_validate({"data": form_data.config})
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

    DEFAULT_MODELS: Optional[str]
    MODEL_ORDER_LIST: Optional[list[str]]


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
    if config_db is not None:
        config_db.data.ui.default_models = form_data.DEFAULT_MODELS
        config_db.data.ui.language_model_order_list = form_data.MODEL_ORDER_LIST or []
    else:
        config_db = Config.model_validate(
            {
                "data": {
                    "ui": {
                        "default_models": form_data.DEFAULT_MODELS,
                        "language_model_order_list": form_data.MODEL_ORDER_LIST or [],
                    }
                }
            }
        )
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
    if config_db is not None:
        config_db.data.ui.prompt_suggestions = suggestions
    else:
        config_db = Config.model_validate(
            {"data": {"ui": {"prompt_suggestions": suggestions}}}
        )
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
    if config_db is not None:
        config_db.data.ui.banners = banners
    else:
        config_db = Config.model_validate({"data": {"ui": {"banners": banners}}})
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
