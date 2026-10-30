from unittest.mock import AsyncMock, PropertyMock, patch
from app.cloud.manager import cloud_manager
from app.cloud.models import AgentSettings
from app.cloud import crypto


def test_cloud_status_unregistered(client):
    response = client.get("/api/cloud/status")
    assert response.status_code == 200
    data = response.json()
    assert data["registered"] is False
    assert data["connected"] is False
    assert "not registered" in data["message"].lower()


def test_cloud_register_success(client, db):
    with patch.object(cloud_manager.connection_manager, "notify_registration", new_callable=AsyncMock) as mock_notify:
        response = client.post(
            "/api/cloud/register",
            json={"environment_token": "env_token_secret_test_123"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "registered"
        mock_notify.assert_awaited_once()

    # Verifica no banco que foi salvo e criptografado
    settings = db.query(AgentSettings).first()
    assert settings is not None
    assert settings.environment_token_encrypted is not None
    assert crypto.decrypt(settings.environment_token_encrypted) == "env_token_secret_test_123"


def test_cloud_status_registered_and_connected(client, db):
    # Insere settings com token criptografado
    settings = AgentSettings(
        environment_token_encrypted=crypto.encrypt("token-valido-123"),
        cloud_environment_id="env_abc_999",
    )
    db.add(settings)
    db.commit()

    # Simula status de conectado no WebSocket utilizando PropertyMock
    with patch("app.cloud.websocket_client.CloudWebSocketClient.is_connected", new_callable=PropertyMock, return_value=True):
        response = client.get("/api/cloud/status")
        assert response.status_code == 200
        data = response.json()
        assert data["registered"] is True
        assert data["connected"] is True
        assert data["cloud_environment_id"] == "env_abc_999"
