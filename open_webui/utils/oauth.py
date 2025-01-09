"""OAuth utilities."""

import base64
import mimetypes
import uuid
from typing import Annotated, Literal, cast

import aiohttp
from authlib.integrations.starlette_client import OAuth
from authlib.oidc.core import UserInfo
from fastapi import Depends, HTTPException, status
from loguru import logger
from starlette.responses import RedirectResponse

from open_webui.config import ConfigDep, UserRole
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import env
from open_webui.models.auths import Auths
from open_webui.models.groups import GroupModel, Groups, GroupUpdateForm
from open_webui.models.users import Users
from open_webui.utils.auth import create_token, get_password_hash
from open_webui.utils.webhook import post_webhook


class OAuthManager:
    """OAuth Manager."""

    def __init__(self, config: ConfigDep):  # noqa: D107
        self.oauth = OAuth()
        self.enable_signup = config.oauth.enable_signup
        self.merge_accounts_by_email = config.oauth.merge_accounts_by_email
        self.jwt_expiry = config.auth.jwt_expiry
        self.webhook_url = config.webhook_url
        self.username_claim = config.oauth.oidc.username_claim
        self.picture_claim = config.oauth.oidc.avatar_claim
        self.email_claim = config.oauth.oidc.email_claim
        self.group_claim = config.oauth.oidc.group_claim
        self.config = config.oauth
        self.default_user_role: UserRole = config.ui.default_user_role
        for provider_name, provider_config in self.config.providers.items():
            self.oauth.register(
                name=provider_name,
                client_id=provider_config["client_id"],
                client_secret=provider_config["client_secret"],
                server_metadata_url=provider_config["server_metadata_url"],
                client_kwargs={
                    "scope": provider_config["scope"],
                },
                redirect_uri=provider_config["redirect_uri"],
            )

    def get_client(self, provider_name: str):
        """Get the OAuth client for the given provider."""
        return self.oauth.create_client(provider_name)

    def get_user_role(self, user, user_data) -> Literal["admin", "user", "pending"]:
        """Get the role for the user based on the OAuth data."""
        if user and Users.get_num_users() == 1:
            # If the user is the only user, assign the role "admin" - actually repairs role for single user on login
            return "admin"
        if not user and Users.get_num_users() == 0:
            # If there are no users, assign the role "admin", as the first user will be an admin
            return "admin"

        role: UserRole
        if self.config.enable_role_mapping:
            oauth_claim = self.config.roles_claim
            oauth_allowed_roles = self.config.allowed_roles
            oauth_admin_roles = self.config.admin_roles
            oauth_roles = None
            role = "pending"  # Default/fallback role if no matching roles are found

            # Next block extracts the roles from the user data, accepting nested claims of any depth
            if oauth_claim and oauth_allowed_roles and oauth_admin_roles:
                claim_data = user_data
                nested_claims = oauth_claim.split(".")
                for nested_claim in nested_claims:
                    claim_data = claim_data.get(nested_claim, {})
                oauth_roles = claim_data if isinstance(claim_data, list) else None

            # If any roles are found, check if they match the allowed or admin roles
            if oauth_roles:
                # If role management is enabled, and matching roles are provided, use the roles
                for allowed_role in oauth_allowed_roles:
                    # If the user has any of the allowed roles, assign the role "user"
                    if allowed_role in oauth_roles:
                        role = "user"
                        break
                for admin_role in oauth_admin_roles:
                    # If the user has any of the admin roles, assign the role "admin"
                    if admin_role in oauth_roles:
                        role = "admin"
                        break
        else:
            if not user:
                # If role management is disabled, use the default role for new users
                role = self.default_user_role
            else:
                # If role management is disabled, use the existing role for existing users
                role = cast(UserRole, user.role)

        return role

    def update_user_groups(self, user, user_data, default_permissions):
        """Update the user's groups based on the OAuth data."""
        oauth_claim = self.group_claim

        user_oauth_groups: list[str] = user_data.get(oauth_claim, list())
        user_current_groups: list[GroupModel] = Groups.get_groups_by_member_id(user.id)
        all_available_groups: list[GroupModel] = Groups.get_groups()

        # Remove groups that user is no longer a part of
        for group_model in user_current_groups:
            if group_model.name not in user_oauth_groups:
                # Remove group from user

                user_ids = group_model.user_ids
                user_ids = [i for i in user_ids if i != user.id]

                # In case a group is created, but perms are never assigned to the group by hitting "save"
                group_permissions = group_model.permissions
                if not group_permissions:
                    group_permissions = default_permissions

                update_form = GroupUpdateForm(
                    name=group_model.name,
                    description=group_model.description,
                    permissions=group_permissions,
                    user_ids=user_ids,
                )
                Groups.update_group_by_id(
                    id=group_model.id, form_data=update_form, overwrite=False
                )

        # Add user to new groups
        for group_model in all_available_groups:
            if group_model.name in user_oauth_groups and not any(
                gm.name == group_model.name for gm in user_current_groups
            ):
                # Add user to group

                user_ids = group_model.user_ids
                user_ids.append(user.id)

                # In case a group is created, but perms are never assigned to the group by hitting "save"
                group_permissions = group_model.permissions
                if not group_permissions:
                    group_permissions = default_permissions

                update_form = GroupUpdateForm(
                    name=group_model.name,
                    description=group_model.description,
                    permissions=group_permissions,
                    user_ids=user_ids,
                )
                Groups.update_group_by_id(
                    id=group_model.id, form_data=update_form, overwrite=False
                )

    async def handle_login(self, provider: str, request):
        """Handle the login process for the given OAuth provider."""
        if provider not in self.config.providers:
            raise HTTPException(404)
        # If the provider has a custom redirect URL, use that, otherwise automatically generate one
        redirect_uri = self.config.providers[provider].get(
            "redirect_uri"
        ) or request.url_for("oauth_callback", provider=provider)
        client = self.get_client(provider)
        if client is None:
            raise HTTPException(404)
        return await client.authorize_redirect(request, redirect_uri)

    async def handle_callback(self, provider, request, response):
        """Handle the callback process for the given OAuth provider."""
        if provider not in self.config.providers:
            raise HTTPException(404)
        client = self.get_client(provider)
        try:
            token = await client.authorize_access_token(request)  # type: ignore
        except Exception as e:
            logger.warning(f"OAuth callback error: {e}")
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)
        user_data: UserInfo = token["userinfo"]
        if not user_data:
            user_data: UserInfo = await client.userinfo(token=token)  # type: ignore
        if not user_data:
            logger.warning(f"OAuth callback failed, user data is missing: {token}")
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

        sub = user_data.get("sub")
        if not sub:
            logger.warning(f"OAuth callback failed, sub is missing: {user_data}")
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)
        provider_sub = f"{provider}@{sub}"
        email_claim = self.email_claim
        email = user_data.get(email_claim, "").lower()
        # We currently mandate that email addresses are provided
        if not email:
            logger.warning(f"OAuth callback failed, email is missing: {user_data}")
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)
        if (
            "*" not in self.config.allowed_domains
            and email.split("@")[-1] not in self.config.allowed_domains
        ):
            logger.warning(
                f"OAuth callback failed, e-mail domain is not in the list of allowed domains: {user_data}"
            )
            raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

        # Check if the user exists
        user = Users.get_user_by_oauth_sub(provider_sub)

        if not user:
            # If the user does not exist, check if merging is enabled
            if self.merge_accounts_by_email:
                # Check if the user exists by email
                user = Users.get_user_by_email(email)
                if user:
                    # Update the user with the new oauth sub
                    Users.update_user_oauth_sub_by_id(user.id, provider_sub)

        if user:
            determined_role = self.get_user_role(user, user_data)
            if user.role != determined_role:
                Users.update_user_role_by_id(user.id, determined_role)

        if not user:
            # If the user does not exist, check if signups are enabled
            if self.enable_signup:
                # Check if an existing user with the same email already exists
                existing_user = Users.get_user_by_email(
                    user_data.get("email", "").lower()
                )
                if existing_user:
                    raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

                picture_claim = self.picture_claim
                picture_url = user_data.get(picture_claim, "")
                if picture_url:
                    # Download the profile image into a base64 string
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(picture_url) as resp:
                                picture = await resp.read()
                                base64_encoded_picture = base64.b64encode(
                                    picture
                                ).decode("utf-8")
                                guessed_mime_type = mimetypes.guess_type(picture_url)[0]
                                if guessed_mime_type is None:
                                    # assume JPG, browsers are tolerant enough of image formats
                                    guessed_mime_type = "image/jpeg"
                                picture_url = f"data:{guessed_mime_type};base64,{base64_encoded_picture}"
                    except Exception as e:
                        logger.error(
                            f"Error downloading profile image '{picture_url}': {e}"
                        )
                        picture_url = ""
                if not picture_url:
                    picture_url = "/user.png"
                username_claim = self.username_claim

                role = self.get_user_role(None, user_data)

                user = Auths.insert_new_auth(
                    email=email,
                    password=get_password_hash(str(uuid.uuid4())),
                    name=user_data.get(username_claim, "User"),
                    profile_image_url=picture_url,
                    role=role,
                    oauth_sub=provider_sub,
                )
                assert user is not None

                if self.webhook_url:
                    post_webhook(
                        cast(str, self.webhook_url),
                        f"New user {user.name} signed up",
                        {
                            "action": "signup",
                            "message": f"New user {user.name} signed up",
                            "user": user.model_dump_json(exclude_none=True),
                        },
                    )
            else:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED
                )

        jwt_token = create_token(
            data={"id": user.id},
            expires_delta=self.jwt_expiry,
        )

        if self.config.enable_group_mapping:
            self.update_user_groups(
                user=user,
                user_data=user_data,
                default_permissions=request.app.state.config.USER_PERMISSIONS,
            )

        # Set the cookie token
        response.set_cookie(
            key="token",
            value=jwt_token,
            httponly=True,  # Ensures the cookie is not accessible via JavaScript
            samesite=env.WEBUI_SESSION_COOKIE_SAME_SITE,
            secure=env.WEBUI_SESSION_COOKIE_SECURE,
        )

        if self.enable_signup:
            oauth_id_token = token.get("id_token")
            response.set_cookie(
                key="oauth_id_token",
                value=oauth_id_token,
                httponly=True,
                samesite=env.WEBUI_SESSION_COOKIE_SAME_SITE,
                secure=env.WEBUI_SESSION_COOKIE_SECURE,
            )
        # Redirect back to the frontend with the JWT token
        redirect_url = f"{request.base_url}auth#token={jwt_token}"
        return RedirectResponse(url=redirect_url, headers=response.headers)


OAuthManagerDep = Annotated[OAuthManager, Depends()]
