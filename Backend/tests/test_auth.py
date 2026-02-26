import asyncio
import logging
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
    assert data["role"] == "user"
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


# ──────────────────────────────────────────────
# Password reset helpers
# ──────────────────────────────────────────────

async def _request_reset_token(client, caplog, email: str) -> str:
    """Request a password reset via API and extract the token from logs."""
    with caplog.at_level(logging.INFO, logger="app.services.password_reset_service"):
        caplog.clear()
        await client.post("/api/v1/auth/password-reset/request", json={"email": email})
    for record in caplog.records:
        if "token=" in record.message:
            return record.message.split("token=")[1]
    raise AssertionError("Reset token not found in logs")


# ──────────────────────────────────────────────
# Password reset tests
# ──────────────────────────────────────────────

async def test_request_reset_existing_email(client):
    await client.post("/api/v1/users/", json={
        "email": "reqreset@test.com", "username": "reqresetuser",
        "name": "Test User", "password": "StrongPass1"
    })
    response = await client.post("/api/v1/auth/password-reset/request", json={
        "email": "reqreset@test.com"
    })
    assert response.status_code == 200
    assert response.json()["message"] == "If the email exists, a reset link has been sent."


async def test_request_reset_nonexistent_email(client):
    """Should still return 200 to prevent email enumeration."""
    response = await client.post("/api/v1/auth/password-reset/request", json={
        "email": "nobody@test.com"
    })
    assert response.status_code == 200
    assert response.json()["message"] == "If the email exists, a reset link has been sent."


async def test_confirm_reset_valid_token(client, caplog):
    """Full flow: request reset -> confirm with new password -> login with new password."""
    await client.post("/api/v1/users/", json={
        "email": "confirm@test.com", "username": "confirmuser",
        "name": "Confirm User", "password": "StrongPass1"
    })
    raw_token = await _request_reset_token(client, caplog, "confirm@test.com")

    response = await client.post("/api/v1/auth/password-reset/confirm", json={
        "token": raw_token,
        "new_password": "NewStrong1"
    })
    assert response.status_code == 200
    assert response.json()["message"] == "Password has been reset successfully."

    # Old password should no longer work
    login_resp = await client.post("/api/v1/auth/login", data={
        "username": "confirmuser",
        "password": "StrongPass1"
    })
    assert login_resp.status_code == 401

    # New password should work
    login_resp = await client.post("/api/v1/auth/login", data={
        "username": "confirmuser",
        "password": "NewStrong1"
    })
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


async def test_confirm_reset_invalid_token(client):
    response = await client.post("/api/v1/auth/password-reset/confirm", json={
        "token": "totally-invalid-token",
        "new_password": "NewStrong1"
    })
    assert response.status_code == 400


async def test_confirm_reset_used_token(client, caplog):
    """Using the same reset token twice should fail."""
    await client.post("/api/v1/users/", json={
        "email": "used@test.com", "username": "useduser",
        "name": "Used User", "password": "StrongPass1"
    })
    raw_token = await _request_reset_token(client, caplog, "used@test.com")

    resp1 = await client.post("/api/v1/auth/password-reset/confirm", json={
        "token": raw_token,
        "new_password": "NewStrong1"
    })
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/auth/password-reset/confirm", json={
        "token": raw_token,
        "new_password": "AnotherPass1"
    })
    assert resp2.status_code == 400


async def test_confirm_reset_weak_password(client, caplog):
    """Password validation should apply on reset too."""
    await client.post("/api/v1/users/", json={
        "email": "weakrst@test.com", "username": "weakreset",
        "name": "Weak User", "password": "StrongPass1"
    })
    raw_token = await _request_reset_token(client, caplog, "weakrst@test.com")

    response = await client.post("/api/v1/auth/password-reset/confirm", json={
        "token": raw_token,
        "new_password": "short"
    })
    assert response.status_code == 422


async def test_refresh_tokens_revoked_after_reset(client, caplog):
    """After password reset, existing refresh tokens should be invalid."""
    await client.post("/api/v1/users/", json={
        "email": "revoke@test.com", "username": "revokeuser",
        "name": "Revoke User", "password": "StrongPass1"
    })
    login_resp = await client.post("/api/v1/auth/login", data={
        "username": "revokeuser",
        "password": "StrongPass1"
    })
    old_refresh_token = login_resp.json()["refresh_token"]

    raw_token = await _request_reset_token(client, caplog, "revoke@test.com")
    await client.post("/api/v1/auth/password-reset/confirm", json={
        "token": raw_token,
        "new_password": "NewStrong1"
    })

    resp = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": old_refresh_token
    })
    assert resp.status_code == 401