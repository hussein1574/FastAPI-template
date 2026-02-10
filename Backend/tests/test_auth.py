import asyncio
import pytest

pytestmark = pytest.mark.asyncio


async def test_register_user(client):
    response = await client.post("/api/v1/users/", json={
        "email": "test@test.com",
        "username": "testuser",
        "name": "Test User",
        "password": "StrongPass1"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@test.com"
    assert data["username"] == "testuser"
    assert "id" in data


async def test_register_duplicate_email(client):
    payload = {"email": "dupe@test.com", "username": "user1", "name": "User", "password": "StrongPass1"}
    await client.post("/api/v1/users/", json=payload)
    payload["username"] = "user2"
    response = await client.post("/api/v1/users/", json=payload)
    assert response.status_code == 409


async def test_register_weak_password(client):
    response = await client.post("/api/v1/users/", json={
        "email": "weak@test.com",
        "username": "weakuser",
        "name": "Weak",
        "password": "short"
    })
    assert response.status_code == 422  # Pydantic validation error


async def test_login_success(client):
    # Register first
    await client.post("/api/v1/users/", json={
        "email": "login@test.com",
        "username": "loginuser",
        "name": "Login User",
        "password": "StrongPass1"
    })
    # Login
    response = await client.post("/api/v1/auth/login", data={
        "username": "loginuser",
        "password": "StrongPass1"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client):
    await client.post("/api/v1/users/", json={
        "email": "wrong@test.com",
        "username": "wronguser",
        "name": "Wrong",
        "password": "StrongPass1"
    })
    response = await client.post("/api/v1/auth/login", data={
        "username": "wronguser",
        "password": "WrongPass1"
    })
    assert response.status_code == 401


async def test_get_me_authenticated(client):
    await client.post("/api/v1/users/", json={
        "email": "me@test.com",
        "username": "meuser",
        "name": "Me User",
        "password": "StrongPass1"
    })
    login = await client.post("/api/v1/auth/login", data={
        "username": "meuser",
        "password": "StrongPass1"
    })
    token = login.json()["access_token"]
    response = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@test.com"


async def test_get_me_unauthenticated(client):
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


async def test_refresh_token(client):
    await client.post("/api/v1/users/", json={
        "email": "refresh@test.com",
        "username": "refreshuser",
        "name": "Refresh",
        "password": "StrongPass1"
    })
    login = await client.post("/api/v1/auth/login", data={
        "username": "refreshuser",
        "password": "StrongPass1"
    })
    refresh_token = login.json()["refresh_token"]
    await asyncio.sleep(1.1)  # Ensure the new token has a different timestamp
    response = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert response.status_code == 200
    assert "access_token" in response.json()