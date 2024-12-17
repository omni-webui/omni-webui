import os
from urllib.parse import urlencode

import pytest

from omni_webui.config import Settings


def test_get_env(tmp_path):
    os.environ["WEBUI_SECRET_KEY"] = "1"
    settings = Settings()
    assert settings.secret_key == "1"
    del os.environ["WEBUI_SECRET_KEY"]
    settings = Settings(_secrets_dir=tmp_path)  # type: ignore
    assert f"s={settings.secret_key}" == urlencode(
        {"s": settings.secret_key}
    ), "Secret key is not URL safe"
    assert (
        len(settings.secret_key) >= 12
    ), "Secret key is not greater than 12 characters"


@pytest.mark.anyio
async def test_api_config(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    assert not response.json().get("onboarding", False)


@pytest.mark.anyio
async def test_api_config_no_user(no_users_client):
    response = no_users_client.get("/api/config")
    assert response.status_code == 200
    assert response.json().get("onboarding")
