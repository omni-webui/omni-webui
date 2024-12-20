from fastapi import APIRouter
from sqlmodel import col, func, select

from ... import __version__
from ...deps import EnvDepends, SessionDepends
from ...models.config import ConfigDepends
from ...models.user import User, UserDepends
from .models import list_models
from .v1 import router as v1_router

router = APIRouter()
router.include_router(v1_router, prefix="/v1")

router.get("/models")(list_models)


@router.get("/config")
async def retrieve_config(
    *,
    env: EnvDepends,
    session: SessionDepends,
    user: UserDepends,
    config: ConfigDepends,
):
    response = {
        "status": True,
        "name": env.webui_name,
        "version": __version__,
        "default_locale": config.ui.default_locale,
        "oauth": {
            "providers": {
                name: provider.get("name", name)
                for name, provider in config.oauth.providers.items()
            }
        },
        "features": {
            "auth": env.webui_auth,
            "auth_trusted_header": False,
            "enable_ldap": config.ldap.enable,
            "enable_api_key": config.auth.api_key.enable,
            "enable_signup": config.ui.enable_signup,
            "enable_login_form": config.ui.ENABLE_LOGIN_FORM,
        },
    }

    if user is None:
        user_count = (await session.exec(select(func.count(col(User.id))))).one()
        if user_count == 0:
            response |= {"onboarding": True}
    else:
        response["features"] |= {
            "enable_web_search": config.rag.web.search.enable,
            "enable_image_generation": config.image_generation.enable,
            "enable_community_sharing": config.ui.enable_community_sharing,
            "enable_message_rating": config.ui.enable_message_rating,
            "enable_admin_export": env.enable_admin_export,
            "enable_admin_chat_access": env.enable_admin_chat_access,
        }
        response |= {
            "default_models": config.ui.default_models,
            "default_prompt_suggestions": config.ui.prompt_suggestions,
            "audio": {
                "tts": config.audio.tts.model_dump(
                    include={"engine", "voice", "split_on"}
                ),
                "stt": config.audio.stt.model_dump(include={"engine"}),
            },
            "file": config.rag.file.model_dump(),
            "permissions": config.user.permissions.model_dump(),
        }
    return response
