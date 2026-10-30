import pytest


def test_login_success(client, test_user):
    response = client.post(
        "/api/auth/login",
        json={
            "email": test_user.email,
            "password": "Secret123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"].lower() == "bearer"


def test_login_invalid_password(client, test_user):
    response = client.post(
        "/api/auth/login",
        json={
            "email": test_user.email,
            "password": "WrongPassword!",
        },
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_nonexistent_email(client):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "notfound@example.com",
            "password": "AnyPassword123!",
        },
    )
    assert response.status_code == 401


def test_auth_me_with_valid_token(client, auth_headers, test_user):
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user.id
    assert data["email"] == test_user.email
    assert data["username"] == test_user.username


def test_auth_me_without_token_returns_401(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_token_refresh_flow(client, test_user):
    # 1. Login inicial
    login_resp = client.post(
        "/api/auth/login",
        json={
            "email": test_user.email,
            "password": "Secret123!",
        },
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    # 2. Requisitar renovação com refresh token
    refresh_resp = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    new_data = refresh_resp.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data


def test_token_refresh_invalid_token(client):
    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": "invalid.refresh.token"},
    )
    assert response.status_code == 401
