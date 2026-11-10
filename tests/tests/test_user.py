import pytest
from httpx import AsyncClient

from app.database.models import User, UserRole


def signup_payload(**overrides):
    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "username": "johndoe",
        "email": "john@example.com",
        "password": "StrongPassword123!",
        "requested_role": UserRole.DEVELOPER,
        "requested_from": 1,
        "request_note": "Joining as a developer",
    }
    payload.update(overrides)

    return payload


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient, supervisor_user: User):
    response = await client.post(
        "/user/signup",
        json=signup_payload(requested_from=supervisor_user.id),
    )

    assert response.status_code == 201

    data = response.json()

    assert data == {
        "id": data["id"],
        "username": "johndoe",
        "email": "john@example.com",
    }

    assert response.cookies.get("access_token") is not None


@pytest.mark.asyncio
async def test_signup_missing_requested_from(client: AsyncClient):
    response = await client.post(
        "/user/signup",
        json=signup_payload(requested_from=None),
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_signup_invalid_password(client: AsyncClient):
    response = await client.post(
        "/user/signup",
        json=signup_payload(password="123"),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_developer_without_requested_from(client: AsyncClient):
    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "username": "johndoe",
        "email": "john@example.com",
        "password": "StrongPassword123!",
        "requested_role": UserRole.DEVELOPER,
    }

    response = await client.post("/user/signup", json=payload)

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_join_requests_without_authentication(client: AsyncClient):
    response = await client.get("/user/join-requests")

    assert response.status_code == 401
    assert response.json()["detail"] == "Session expired, please login again."


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    response = await client.post(
        "/user/login",
        json={
            "email": "unknown@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


@pytest.mark.asyncio
async def test_login_missing_fields(client: AsyncClient):
    response = await client.post(
        "/user/login",
        json={"email": "john@example.com"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_active_supervisors(client: AsyncClient):
    response = await client.get("/user/supervisors")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
