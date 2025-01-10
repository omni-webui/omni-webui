"""Auths router."""

import datetime
import logging
import re
import time
import uuid
from ssl import CERT_REQUIRED, PROTOCOL_TLS
from typing import Optional

from aiohttp import ClientSession
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from ldap3 import ALL, Connection, Server, Tls
from ldap3.utils.conv import escape_filter_chars
from pydantic import BaseModel

from open_webui.config import (
    ConfigDBDep,
    ConfigDep,
    UserRole,
    parse_duration,
)
from open_webui.constants import ERROR_MESSAGES, WEBHOOK_MESSAGES
from open_webui.env import (
    SRC_LOG_LEVELS,
    WEBUI_AUTH_TRUSTED_EMAIL_HEADER,
    WEBUI_AUTH_TRUSTED_NAME_HEADER,
    env,
)
from open_webui.models import SessionDep
from open_webui.models.auths import (
    AddUserForm,
    ApiKey,
    Auths,
    LdapForm,
    SigninForm,
    SigninResponse,
    SignupForm,
    Token,
    UpdatePasswordForm,
    UpdateProfileForm,
    UserResponse,
)
from open_webui.models.users import Users
from open_webui.utils.access_control import get_permissions
from open_webui.utils.auth import (
    create_api_key,
    create_token,
    get_admin_user,
    get_current_user,
    get_password_hash,
    get_verified_user,
)
from open_webui.utils.misc import validate_email_format
from open_webui.utils.webhook import post_webhook

router = APIRouter()

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


class SessionUserResponse(Token, UserResponse):
    """Session user response."""

    expires_at: Optional[int] = None
    permissions: Optional[dict] = None


@router.get("/", response_model=SessionUserResponse)
async def get_session_user(
    request: Request,
    response: Response,
    config: ConfigDep,
    user=Depends(get_current_user),
):
    """Get session user."""
    expires_delta = config.auth.jwt_expiry
    expires_at = None
    if expires_delta:
        expires_at = int(time.time()) + int(expires_delta.total_seconds())

    token = create_token(
        data={"id": user.id},
        expires_delta=expires_delta,
    )

    datetime_expires_at = (
        datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
        if expires_at
        else None
    )

    # Set the cookie token
    response.set_cookie(
        key="token",
        value=token,
        expires=datetime_expires_at,
        httponly=True,  # Ensures the cookie is not accessible via JavaScript
        samesite=env.WEBUI_SESSION_COOKIE_SAME_SITE,
        secure=env.WEBUI_SESSION_COOKIE_SECURE,
    )

    user_permissions = get_permissions(
        user.id, request.app.state.config.USER_PERMISSIONS
    )

    return {
        "token": token,
        "token_type": "Bearer",
        "expires_at": expires_at,
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "profile_image_url": user.profile_image_url,
        "permissions": user_permissions,
    }


@router.post("/update/profile", response_model=UserResponse)
async def update_profile(
    form_data: UpdateProfileForm, session_user=Depends(get_verified_user)
):
    """Update profile."""
    if session_user:
        user = Users.update_user_by_id(
            session_user.id,
            {"profile_image_url": form_data.profile_image_url, "name": form_data.name},
        )
        if user:
            return user
        else:
            raise HTTPException(400, detail="Failed to update profile")
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


@router.post("/update/password", response_model=bool)
async def update_password(
    form_data: UpdatePasswordForm, session_user=Depends(get_current_user)
):
    """Update password."""
    if WEBUI_AUTH_TRUSTED_EMAIL_HEADER:
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


@router.post("/ldap", response_model=SigninResponse)
async def ldap_auth(
    request: Request, response: Response, config: ConfigDep, form_data: LdapForm
):
    """LDAP authentication."""
    ENABLE_LDAP = request.app.state.config.ENABLE_LDAP
    LDAP_SERVER_HOST = request.app.state.config.LDAP_SERVER_HOST
    LDAP_SERVER_PORT = request.app.state.config.LDAP_SERVER_PORT
    LDAP_ATTRIBUTE_FOR_USERNAME = request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME
    LDAP_SEARCH_BASE = request.app.state.config.LDAP_SEARCH_BASE
    LDAP_SEARCH_FILTERS = request.app.state.config.LDAP_SEARCH_FILTERS
    LDAP_APP_DN = request.app.state.config.LDAP_APP_DN
    LDAP_APP_PASSWORD = request.app.state.config.LDAP_APP_PASSWORD
    LDAP_USE_TLS = request.app.state.config.LDAP_USE_TLS
    LDAP_CA_CERT_FILE = request.app.state.config.LDAP_CA_CERT_FILE
    LDAP_CIPHERS = (
        request.app.state.config.LDAP_CIPHERS
        if request.app.state.config.LDAP_CIPHERS
        else "ALL"
    )

    if not ENABLE_LDAP:
        raise HTTPException(400, detail="LDAP authentication is not enabled")

    try:
        tls = Tls(
            validate=CERT_REQUIRED,
            version=PROTOCOL_TLS,
            ca_certs_file=LDAP_CA_CERT_FILE,
            ciphers=LDAP_CIPHERS,
        )
    except Exception as e:
        log.error(f"An error occurred on TLS: {str(e)}")
        raise HTTPException(400, detail=str(e))

    try:
        server = Server(
            host=LDAP_SERVER_HOST,
            port=LDAP_SERVER_PORT,
            get_info=ALL,
            use_ssl=LDAP_USE_TLS,
            tls=tls,
        )
        connection_app = Connection(
            server,
            LDAP_APP_DN,
            LDAP_APP_PASSWORD,
            auto_bind="NONE",
            authentication="SIMPLE",
        )
        if not connection_app.bind():
            raise HTTPException(400, detail="Application account bind failed")

        search_success = connection_app.search(
            search_base=LDAP_SEARCH_BASE,
            search_filter=f"(&({LDAP_ATTRIBUTE_FOR_USERNAME}={escape_filter_chars(form_data.user.lower())}){LDAP_SEARCH_FILTERS})",
            attributes=[f"{LDAP_ATTRIBUTE_FOR_USERNAME}", "mail", "cn"],
        )

        if not search_success:
            raise HTTPException(400, detail="User not found in the LDAP server")

        entry = connection_app.entries[0]
        username = str(entry[f"{LDAP_ATTRIBUTE_FOR_USERNAME}"]).lower()
        mail = str(entry["mail"])
        cn = str(entry["cn"])
        user_dn = entry.entry_dn

        if username == form_data.user.lower():
            connection_user = Connection(
                server,
                user_dn,
                form_data.password,
                auto_bind="NONE",
                authentication="SIMPLE",
            )
            if not connection_user.bind():
                raise HTTPException(400, f"Authentication failed for {form_data.user}")

            user = Users.get_user_by_email(mail)
            if not user:
                try:
                    role = (
                        "admin"
                        if Users.get_num_users() == 0
                        else config.ui.default_user_role
                    )

                    user = Auths.insert_new_auth(
                        email=mail, password=str(uuid.uuid4()), name=cn, role=role
                    )

                    if not user:
                        raise HTTPException(
                            500, detail=ERROR_MESSAGES.CREATE_USER_ERROR
                        )

                except HTTPException:
                    raise
                except Exception as e:
                    raise HTTPException(500, detail=str(e))

            user = Auths.authenticate_user_by_trusted_header(mail)

            if user:
                token = create_token(
                    data={"id": user.id},
                    expires_delta=config.auth.jwt_expiry,
                )

                # Set the cookie token
                response.set_cookie(
                    key="token",
                    value=token,
                    httponly=True,  # Ensures the cookie is not accessible via JavaScript
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
        else:
            raise HTTPException(
                400,
                f"User {form_data.user} does not match the record. Search result: {str(entry[f'{LDAP_ATTRIBUTE_FOR_USERNAME}'])}",
            )
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@router.post("/signin", response_model=SessionUserResponse)
async def signin(
    request: Request,
    response: Response,
    form_data: SigninForm,
    session: SessionDep,
    config_db: ConfigDBDep,
):
    """Sign in."""
    if WEBUI_AUTH_TRUSTED_EMAIL_HEADER:
        if WEBUI_AUTH_TRUSTED_EMAIL_HEADER not in request.headers:
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_TRUSTED_HEADER)

        trusted_email = request.headers[WEBUI_AUTH_TRUSTED_EMAIL_HEADER].lower()
        trusted_name = trusted_email
        if WEBUI_AUTH_TRUSTED_NAME_HEADER:
            trusted_name = request.headers.get(
                WEBUI_AUTH_TRUSTED_NAME_HEADER, trusted_email
            )
        if not Users.get_user_by_email(trusted_email.lower()):
            await signup(
                request,
                response,
                session,
                config_db,
                SignupForm(
                    email=trusted_email, password=str(uuid.uuid4()), name=trusted_name
                ),
            )
        user = Auths.authenticate_user_by_trusted_header(trusted_email)
    elif not env.WEBUI_AUTH:
        admin_email = "admin@localhost"
        admin_password = "admin"

        if Users.get_user_by_email(admin_email.lower()):
            user = Auths.authenticate_user(admin_email.lower(), admin_password)
        else:
            if Users.get_num_users() != 0:
                raise HTTPException(400, detail=ERROR_MESSAGES.EXISTING_USERS)

            await signup(
                request,
                response,
                session,
                config_db,
                SignupForm(email=admin_email, password=admin_password, name="User"),
            )

            user = Auths.authenticate_user(admin_email.lower(), admin_password)
    else:
        user = Auths.authenticate_user(form_data.email.lower(), form_data.password)

    if user:
        expires_delta = config_db.data.auth.jwt_expiry
        expires_at = None
        if expires_delta:
            expires_at = int(time.time()) + int(expires_delta.total_seconds())

        token = create_token(
            data={"id": user.id},
            expires_delta=expires_delta,
        )

        datetime_expires_at = (
            datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
            if expires_at
            else None
        )

        # Set the cookie token
        response.set_cookie(
            key="token",
            value=token,
            expires=datetime_expires_at,
            httponly=True,  # Ensures the cookie is not accessible via JavaScript
            samesite=env.WEBUI_SESSION_COOKIE_SAME_SITE,
            secure=env.WEBUI_SESSION_COOKIE_SECURE,
        )

        user_permissions = get_permissions(
            user.id, request.app.state.config.USER_PERMISSIONS
        )

        return {
            "token": token,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "profile_image_url": user.profile_image_url,
            "permissions": user_permissions,
        }
    else:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)


@router.post("/signup", response_model=SessionUserResponse)
async def signup(
    request: Request,
    response: Response,
    session: SessionDep,
    config_db: ConfigDBDep,
    form_data: SignupForm,
):
    """Sign up."""
    config = config_db.data
    if env.WEBUI_AUTH:
        if (
            not config.ui.enable_signup
            or not request.app.state.config.ENABLE_LOGIN_FORM
        ):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED
            )
    else:
        if Users.get_num_users() != 0:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED
            )

    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )

    if Users.get_user_by_email(form_data.email.lower()):
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    role = "admin" if Users.get_num_users() == 0 else config.ui.default_user_role

    if Users.get_num_users() == 0:
        # Disable signup after the first user is created
        config.ui.enable_signup = False

    hashed = get_password_hash(form_data.password)
    user = Auths.insert_new_auth(
        form_data.email.lower(),
        hashed,
        form_data.name,
        form_data.profile_image_url or "/user.png",
        role,
    )

    if user is None:
        raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)

    expires_delta = config.auth.jwt_expiry
    expires_at = None
    if expires_delta:
        expires_at = int(time.time()) + int(expires_delta.total_seconds())

    token = create_token(
        data={"id": user.id},
        expires_delta=expires_delta,
    )

    datetime_expires_at = (
        datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
        if expires_at
        else None
    )

    # Set the cookie token
    response.set_cookie(
        key="token",
        value=token,
        expires=datetime_expires_at,
        httponly=True,  # Ensures the cookie is not accessible via JavaScript
        samesite=env.WEBUI_SESSION_COOKIE_SAME_SITE,
        secure=env.WEBUI_SESSION_COOKIE_SECURE,
    )

    if config.webhook_url:
        post_webhook(
            config.webhook_url,
            WEBHOOK_MESSAGES.USER_SIGNUP(user.name),
            {
                "action": "signup",
                "message": WEBHOOK_MESSAGES.USER_SIGNUP(user.name),
                "user": user.model_dump_json(exclude_none=True),
            },
        )

    user_permissions = get_permissions(
        user.id, request.app.state.config.USER_PERMISSIONS
    )

    config_db.data = config
    session.add(config_db)
    await session.commit()
    return {
        "token": token,
        "token_type": "Bearer",
        "expires_at": expires_at,
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "profile_image_url": user.profile_image_url,
        "permissions": user_permissions,
    }


@router.get("/signout")
async def signout(request: Request, response: Response, config: ConfigDep):
    """Sign out."""
    response.delete_cookie("token")

    if config.oauth.enable_signup:
        oauth_id_token = request.cookies.get("oauth_id_token")
        if oauth_id_token:
            try:
                async with ClientSession() as session:
                    async with session.get(config.oauth.oidc.provider_url) as resp:  # type: ignore
                        if resp.status == 200:
                            openid_data = await resp.json()
                            logout_url = openid_data.get("end_session_endpoint")
                            if logout_url:
                                response.delete_cookie("oauth_id_token")
                                return RedirectResponse(
                                    url=f"{logout_url}?id_token_hint={oauth_id_token}"
                                )
                        else:
                            raise HTTPException(
                                status_code=resp.status,
                                detail="Failed to fetch OpenID configuration",
                            )
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    return {"status": True}


@router.post("/add", response_model=SigninResponse)
async def add_user(form_data: AddUserForm, user=Depends(get_admin_user)):
    """Add user."""
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )

    if Users.get_user_by_email(form_data.email.lower()):
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    try:
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
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@router.get("/admin/details")
async def get_admin_details(
    request: Request, config: ConfigDep, user=Depends(get_current_user)
):
    """Get admin details."""
    if config.auth.admin.show:
        admin_email = config.auth.admin.email
        admin_name = None

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


@router.get("/admin/config")
async def get_admin_config(
    request: Request, config: ConfigDep, user=Depends(get_admin_user)
):
    """Get admin configuration."""
    return {
        "SHOW_ADMIN_DETAILS": config.auth.admin.show,
        "WEBUI_URL": config.webui.url,
        "ENABLE_SIGNUP": config.ui.enable_signup,
        "ENABLE_API_KEY": config.auth.api_key.enable,
        "ENABLE_API_KEY_ENDPOINT_RESTRICTIONS": config.auth.api_key.endpoint_restrictions,
        "API_KEY_ALLOWED_ENDPOINTS": ",".join(config.auth.api_key.allowed_endpoints),
        "ENABLE_CHANNELS": request.app.state.config.ENABLE_CHANNELS,
        "DEFAULT_USER_ROLE": config.ui.default_user_role,
        "JWT_EXPIRES_IN": config.auth.model_dump()["jwt_expiry"],
        "ENABLE_COMMUNITY_SHARING": request.app.state.config.ENABLE_COMMUNITY_SHARING,
        "ENABLE_MESSAGE_RATING": request.app.state.config.ENABLE_MESSAGE_RATING,
    }


class AdminConfig(BaseModel):
    """Admin configuration form."""

    SHOW_ADMIN_DETAILS: bool
    WEBUI_URL: str
    ENABLE_SIGNUP: bool
    ENABLE_API_KEY: bool
    ENABLE_API_KEY_ENDPOINT_RESTRICTIONS: bool
    API_KEY_ALLOWED_ENDPOINTS: str
    ENABLE_CHANNELS: bool
    DEFAULT_USER_ROLE: UserRole
    JWT_EXPIRES_IN: str
    ENABLE_COMMUNITY_SHARING: bool
    ENABLE_MESSAGE_RATING: bool


@router.post("/admin/config")
async def update_admin_config(
    request: Request,
    form_data: AdminConfig,
    config_db: ConfigDBDep,
    session: SessionDep,
    user=Depends(get_admin_user),
):
    """Update admin configuration."""
    config = config_db.data
    config.auth.admin.show = form_data.SHOW_ADMIN_DETAILS
    config.webui.url = form_data.WEBUI_URL
    config.ui.enable_signup = form_data.ENABLE_SIGNUP

    config.auth.api_key.enable = form_data.ENABLE_API_KEY
    config.auth.api_key.endpoint_restrictions = (
        form_data.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS
    )
    config.auth.api_key.allowed_endpoints = (
        [x.strip() for x in form_data.API_KEY_ALLOWED_ENDPOINTS.split(",")]
        if form_data.API_KEY_ALLOWED_ENDPOINTS
        else []
    )

    request.app.state.config.ENABLE_CHANNELS = form_data.ENABLE_CHANNELS

    config.ui.default_user_role = form_data.DEFAULT_USER_ROLE

    pattern = r"^(-1|0|(-?\d+(\.\d+)?)(ms|s|m|h|d|w))$"

    # Check if the input string matches the pattern
    if re.match(pattern, form_data.JWT_EXPIRES_IN):
        config.auth.jwt_expiry = parse_duration(form_data.JWT_EXPIRES_IN)

    request.app.state.config.ENABLE_COMMUNITY_SHARING = (
        form_data.ENABLE_COMMUNITY_SHARING
    )
    request.app.state.config.ENABLE_MESSAGE_RATING = form_data.ENABLE_MESSAGE_RATING
    session.add(config_db)
    await session.commit()

    return {
        "SHOW_ADMIN_DETAILS": config.auth.admin.show,
        "WEBUI_URL": config.webui.url,
        "ENABLE_SIGNUP": config.ui.enable_signup,
        "ENABLE_API_KEY": config.auth.api_key.enable,
        "ENABLE_API_KEY_ENDPOINT_RESTRICTIONS": config.auth.api_key.endpoint_restrictions,
        "API_KEY_ALLOWED_ENDPOINTS": ",".join(config.auth.api_key.allowed_endpoints),
        "ENABLE_CHANNELS": request.app.state.config.ENABLE_CHANNELS,
        "DEFAULT_USER_ROLE": config.ui.default_user_role,
        "JWT_EXPIRES_IN": config.auth.model_dump()["jwt_expiry"],
        "ENABLE_COMMUNITY_SHARING": request.app.state.config.ENABLE_COMMUNITY_SHARING,
        "ENABLE_MESSAGE_RATING": request.app.state.config.ENABLE_MESSAGE_RATING,
    }


class LdapServerConfig(BaseModel):
    """LDAP server configuration."""

    label: str
    host: str
    port: Optional[int] = None
    attribute_for_username: str = "uid"
    app_dn: str
    app_dn_password: str
    search_base: str
    search_filters: str = ""
    use_tls: bool = True
    certificate_path: Optional[str] = None
    ciphers: Optional[str] = "ALL"


@router.get("/admin/config/ldap/server", response_model=LdapServerConfig)
async def get_ldap_server(request: Request, user=Depends(get_admin_user)):
    """Get LDAP server configuration."""
    return {
        "label": request.app.state.config.LDAP_SERVER_LABEL,
        "host": request.app.state.config.LDAP_SERVER_HOST,
        "port": request.app.state.config.LDAP_SERVER_PORT,
        "attribute_for_username": request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME,
        "app_dn": request.app.state.config.LDAP_APP_DN,
        "app_dn_password": request.app.state.config.LDAP_APP_PASSWORD,
        "search_base": request.app.state.config.LDAP_SEARCH_BASE,
        "search_filters": request.app.state.config.LDAP_SEARCH_FILTERS,
        "use_tls": request.app.state.config.LDAP_USE_TLS,
        "certificate_path": request.app.state.config.LDAP_CA_CERT_FILE,
        "ciphers": request.app.state.config.LDAP_CIPHERS,
    }


@router.post("/admin/config/ldap/server")
async def update_ldap_server(
    request: Request, form_data: LdapServerConfig, user=Depends(get_admin_user)
):
    """Update LDAP server configuration."""
    required_fields = [
        "label",
        "host",
        "attribute_for_username",
        "app_dn",
        "app_dn_password",
        "search_base",
    ]
    for key in required_fields:
        value = getattr(form_data, key)
        if not value:
            raise HTTPException(400, detail=f"Required field {key} is empty")

    if form_data.use_tls and not form_data.certificate_path:
        raise HTTPException(
            400, detail="TLS is enabled but certificate file path is missing"
        )

    request.app.state.config.LDAP_SERVER_LABEL = form_data.label
    request.app.state.config.LDAP_SERVER_HOST = form_data.host
    request.app.state.config.LDAP_SERVER_PORT = form_data.port
    request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME = (
        form_data.attribute_for_username
    )
    request.app.state.config.LDAP_APP_DN = form_data.app_dn
    request.app.state.config.LDAP_APP_PASSWORD = form_data.app_dn_password
    request.app.state.config.LDAP_SEARCH_BASE = form_data.search_base
    request.app.state.config.LDAP_SEARCH_FILTERS = form_data.search_filters
    request.app.state.config.LDAP_USE_TLS = form_data.use_tls
    request.app.state.config.LDAP_CA_CERT_FILE = form_data.certificate_path
    request.app.state.config.LDAP_CIPHERS = form_data.ciphers

    return {
        "label": request.app.state.config.LDAP_SERVER_LABEL,
        "host": request.app.state.config.LDAP_SERVER_HOST,
        "port": request.app.state.config.LDAP_SERVER_PORT,
        "attribute_for_username": request.app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME,
        "app_dn": request.app.state.config.LDAP_APP_DN,
        "app_dn_password": request.app.state.config.LDAP_APP_PASSWORD,
        "search_base": request.app.state.config.LDAP_SEARCH_BASE,
        "search_filters": request.app.state.config.LDAP_SEARCH_FILTERS,
        "use_tls": request.app.state.config.LDAP_USE_TLS,
        "certificate_path": request.app.state.config.LDAP_CA_CERT_FILE,
        "ciphers": request.app.state.config.LDAP_CIPHERS,
    }


@router.get("/admin/config/ldap")
async def get_ldap_config(request: Request, user=Depends(get_admin_user)):
    """Get LDAP configuration."""
    return {"ENABLE_LDAP": request.app.state.config.ENABLE_LDAP}


class LdapConfigForm(BaseModel):
    """LDAP configuration form."""

    enable_ldap: Optional[bool] = None


@router.post("/admin/config/ldap")
async def update_ldap_config(
    request: Request, form_data: LdapConfigForm, user=Depends(get_admin_user)
):
    """Update LDAP configuration."""
    request.app.state.config.ENABLE_LDAP = form_data.enable_ldap
    return {"ENABLE_LDAP": request.app.state.config.ENABLE_LDAP}


@router.post("/api_key", response_model=ApiKey)
async def generate_api_key(
    request: Request, config: ConfigDep, user=Depends(get_current_user)
):
    """Create api key."""
    if not config.auth.api_key.enable:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.API_KEY_CREATION_NOT_ALLOWED,
        )

    api_key = create_api_key()
    success = Users.update_user_api_key_by_id(user.id, api_key)

    if success:
        return {
            "api_key": api_key,
        }
    else:
        raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_API_KEY_ERROR)


@router.delete("/api_key", response_model=bool)
async def delete_api_key(user=Depends(get_current_user)):
    """Delete api key."""
    success = Users.update_user_api_key_by_id(user.id, None)
    return success


@router.get("/api_key", response_model=ApiKey)
async def get_api_key(user=Depends(get_current_user)):
    """Get api key."""
    api_key = Users.get_user_api_key_by_id(user.id)
    if api_key:
        return {
            "api_key": api_key,
        }
    else:
        raise HTTPException(404, detail=ERROR_MESSAGES.API_KEY_NOT_FOUND)
