def test_create_user_success(client):
    response = client.post(
        "/api/users",
        json={
            "username": "joaosilva",
            "password": "Password123!",
            "email": "joao@example.com",
            "role": "admin",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "joaosilva"
    assert data["email"] == "joao@example.com"
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data


def test_create_user_duplicate_username_returns_400(client, test_user):
    response = client.post(
        "/api/users",
        json={
            "username": test_user.username,
            "password": "Password123!",
            "email": "another_email@example.com",
            "role": "admin",
        },
    )
    assert response.status_code == 400
    assert "Usuário já existe" in response.json()["detail"]


def test_create_user_duplicate_email_returns_400(client, test_user):
    response = client.post(
        "/api/users",
        json={
            "username": "different_username",
            "password": "Password123!",
            "email": test_user.email,
            "role": "admin",
        },
    )
    assert response.status_code == 400
    assert "Este e-mail já está em uso" in response.json()["detail"]
