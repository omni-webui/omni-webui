import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from omni_webui.apps.webui.models.auths import (
    AddUserForm,
    ApiKey,
    Auths,
    SigninForm,
    SigninResponse,
    SignupForm,
    UpdatePasswordForm,
    UpdateProfileForm,
    UserResponse,
)
from omni_webui.apps.webui.models.users import Users
from omni_webui.config import config, settings
from omni_webui.constants import ERROR_MESSAGES
from omni_webui.utils import (
    create_api_key,
    create_token,
    get_admin_user,
    get_current_user,
    get_password_hash,
)
from omni_webui.utils.misc import parse_duration, validate_email_format
from omni_webui.utils.webhook import post_webhook
from pydantic import BaseModel

router = APIRouter()

############################
# GetSessionUser
############################


@router.get("/", response_model=UserResponse)
async def get_session_user(user=Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "profile_image_url": user.profile_image_url,
    }


############################
# Update Profile
############################


@router.post("/update/profile", response_model=UserResponse)
async def update_profile(
    form_data: UpdateProfileForm, session_user=Depends(get_current_user)
):
    if session_user:
        user = Users.update_user_by_id(
            session_user.id,
            {"profile_image_url": form_data.profile_image_url, "name": form_data.name},
        )
        if user:
            return user
        else:
            raise HTTPException(400, detail=ERROR_MESSAGES.DEFAULT())
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


############################
# Update Password
############################


@router.post("/update/password", response_model=bool)
async def update_password(
    form_data: UpdatePasswordForm, session_user=Depends(get_current_user)
):
    if settings.webui_auth_trusted_email_header:
        raise HTTPException(400, detail=ERROR_MESSAGES.ACTION_PROHIBITED)
    if session_user:
        user = Auths.authenticate_user(session_user.email, form_data.password)

        if user:
            hashed = get_password_hash(form_data.new_password)
            return Auths.update_user_password_by_id(user.id, hashed)
        else:
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_PASSWORD)
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


############################
# SignIn
############################


@router.post("/signin", response_model=SigninResponse)
async def signin(request: Request, form_data: SigninForm):
    if settings.webui_auth_trusted_email_header:
        if settings.webui_auth_trusted_email_header not in request.headers:
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_TRUSTED_HEADER)

        trusted_email = request.headers[
            settings.webui_auth_trusted_email_header
        ].lower()
        if not Users.get_user_by_email(trusted_email.lower()):
            await signup(
                request,
                SignupForm(
                    email=trusted_email, password=str(uuid.uuid4()), name=trusted_email
                ),
            )
        user = Auths.authenticate_user_by_trusted_header(trusted_email)
    elif not settings:
        admin_email = "admin@localhost"
        admin_password = "admin"

        if Users.get_user_by_email(admin_email.lower()):
            user = Auths.authenticate_user(admin_email.lower(), admin_password)
        else:
            if Users.get_num_users() != 0:
                raise HTTPException(400, detail=ERROR_MESSAGES.EXISTING_USERS)

            await signup(
                request,
                SignupForm(email=admin_email, password=admin_password, name="User"),
            )

            user = Auths.authenticate_user(admin_email.lower(), admin_password)
    else:
        user = Auths.authenticate_user(form_data.email.lower(), form_data.password)

    if user:
        token = create_token(
            data={"id": user.id},
            expires_delta=parse_duration(config.auth.jwt_expiry),
        )

        return {
            "token": token,
            "token_type": "Bearer",
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "profile_image_url": user.profile_image_url,
        }
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


############################
# SignUp
############################


@router.post("/signup", response_model=SigninResponse)
async def signup(request: Request, form_data: SignupForm):
    if not config.ui.enable_signup and settings.auth:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED
        )

    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )

    if Users.get_user_by_email(form_data.email.lower()):
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    try:
        role = "admin" if Users.get_num_users() == 0 else config.ui.default_user_role
        hashed = get_password_hash(form_data.password)
        user = Auths.insert_new_auth(
            form_data.email.lower(),
            hashed,
            form_data.name,
            form_data.profile_image_url or "/user.png",
            role,
        )

        if user:
            token = create_token(
                data={"id": user.id},
                expires_delta=parse_duration(config.auth.jwt_expiry),
            )
            # response.set_cookie(key='token', value=token, httponly=True)

            if config.webhook_url:
                message = f"New user signed up: {user.name}"
                post_webhook(
                    config.webhook_url,
                    message,
                    {
                        "action": "signup",
                        "message": message,
                        "user": user.model_dump_json(exclude_none=True),
                    },
                )

            return {
                "token": token,
                "token_type": "Bearer",
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "profile_image_url": user.profile_image_url,
            }
        else:
            raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)
    except Exception as err:
        raise HTTPException(500, detail=ERROR_MESSAGES.DEFAULT(err))


############################
# AddUser
############################


@router.post("/add", response_model=SigninResponse)
async def add_user(form_data: AddUserForm, user=Depends(get_admin_user)):
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )

    if Users.get_user_by_email(form_data.email.lower()):
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    try:
        logger.info(form_data)
        hashed = get_password_hash(form_data.password)
        user = Auths.insert_new_auth(
            form_data.email.lower(),
            hashed,
            form_data.name,
            form_data.profile_image_url or "/user.png",
            form_data.role or "pending",
        )

        if user:
            token = create_token(data={"id": user.id})
            return {
                "token": token,
                "token_type": "Bearer",
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "profile_image_url": user.profile_image_url,
            }
        else:
            raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)
    except Exception as err:
        raise HTTPException(500, detail=ERROR_MESSAGES.DEFAULT(err))


############################
# GetAdminDetails
############################


@router.get("/admin/details")
async def get_admin_details(request: Request, user=Depends(get_current_user)):
    if config.auth.show_admin_details:
        admin_email = config.auth.admin_email
        admin_name = None

        logger.info(admin_email, admin_name)

        if admin_email:
            admin = Users.get_user_by_email(admin_email)
            if admin:
                admin_name = admin.name
        else:
            admin = Users.get_first_user()
            if admin:
                admin_email = admin.email
                admin_name = admin.name

        return {
            "name": admin_name,
            "email": admin_email,
        }
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.ACTION_PROHIBITED)


############################
# ToggleSignUp
############################


@router.get("/admin/config")
async def get_admin_config(request: Request, user=Depends(get_admin_user)):
    return {
        "SHOW_ADMIN_DETAILS": config.auth.show_admin_details,
        "ENABLE_SIGNUP": config.ui.enable_signup,
        "DEFAULT_USER_ROLE": config.ui.default_user_role,
        "JWT_EXPIRES_IN": config.auth.jwt_expiry,
        "ENABLE_COMMUNITY_SHARING": config.ui.enable_community_sharing,
    }


class AdminConfig(BaseModel):
    SHOW_ADMIN_DETAILS: bool
    ENABLE_SIGNUP: bool
    DEFAULT_USER_ROLE: str
    JWT_EXPIRES_IN: str
    ENABLE_COMMUNITY_SHARING: bool


@router.post("/admin/config")
async def update_admin_config(
    request: Request, form_data: AdminConfig, user=Depends(get_admin_user)
):
    config.auth.show_admin_details = form_data.SHOW_ADMIN_DETAILS
    config.ui.enable_signup = form_data.ENABLE_SIGNUP

    if form_data.DEFAULT_USER_ROLE in ["pending", "user", "admin"]:
        config.ui.default_user_role = form_data.DEFAULT_USER_ROLE  # type: ignore[assignment]

    pattern = r"^(-1|0|(-?\d+(\.\d+)?)(ms|s|m|h|d|w))$"

    # Check if the input string matches the pattern
    if re.match(pattern, form_data.JWT_EXPIRES_IN):
        config.auth.jwt_expiry = form_data.JWT_EXPIRES_IN

    config.ui.enable_community_sharing = form_data.ENABLE_COMMUNITY_SHARING

    return {
        "SHOW_ADMIN_DETAILS": config.auth.show_admin_details,
        "ENABLE_SIGNUP": config.ui.enable_signup,
        "DEFAULT_USER_ROLE": config.ui.default_user_role,
        "JWT_EXPIRES_IN": config.auth.jwt_expiry,
        "ENABLE_COMMUNITY_SHARING": config.ui.enable_community_sharing,
    }


############################
# API Key
############################


# create api key
@router.post("/api_key", response_model=ApiKey)
async def create_api_key_(user=Depends(get_current_user)):
    api_key = create_api_key()
    success = Users.update_user_api_key_by_id(user.id, api_key)
    if success:
        return {
            "api_key": api_key,
        }
    else:
        raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_API_KEY_ERROR)


# delete api key
@router.delete("/api_key", response_model=bool)
async def delete_api_key(user=Depends(get_current_user)):
    success = Users.update_user_api_key_by_id(user.id, None)
    return success


# get api key
@router.get("/api_key", response_model=ApiKey)
async def get_api_key(user=Depends(get_current_user)):
    api_key = Users.get_user_api_key_by_id(user.id)
    if api_key:
        return {
            "api_key": api_key,
        }
    else:
        raise HTTPException(404, detail=ERROR_MESSAGES.API_KEY_NOT_FOUND)
