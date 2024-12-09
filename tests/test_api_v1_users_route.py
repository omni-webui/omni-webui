import pytest
from fastapi.testclient import TestClient


@pytest.mark.anyio
async def test_list_users(client: TestClient):
    response = client.get("/api/v1/users")
    assert response.status_code == 200
    assert len(response.json()) > 0
