from unittest.mock import MagicMock, PropertyMock, patch
import pytest

from app.models.container import Container
from app.cloud.models import AgentSettings
from app.cloud import crypto
from app.integrations.proxmox.exceptions import ProxmoxPermissionError


@pytest.fixture
def sample_container(db):
    """Cria um container de teste no banco de dados."""
    ct = Container(
        id="ct-uuid-100",
        container_number=100,
        name="web-server-test",
        password="secret_password",
        status="running",
        cpu=2,
        memory_mb=2048,
    )
    db.add(ct)
    db.commit()
    db.refresh(ct)
    return ct


def test_list_containers_unauthenticated_returns_401(client):
    response = client.get("/api/containers")
    assert response.status_code == 401


def test_list_containers_authenticated_returns_empty_or_items(auth_client):
    response = auth_client.get("/api/containers")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_container_by_id_success(auth_client, sample_container):
    response = auth_client.get(f"/api/containers/{sample_container.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_container.id
    assert data["name"] == "web-server-test"


def test_get_container_not_found(auth_client):
    response = auth_client.get("/api/containers/non-existent-uuid")
    assert response.status_code == 400
    assert "Container não encontrado" in response.json()["detail"]


def test_tailscale_setup_blocked_when_cloud_not_registered(auth_client, sample_container):
    # Sem configurações de Cloud no banco
    response = auth_client.post(f"/api/containers/{sample_container.id}/tailscale/setup")
    assert response.status_code == 400
    assert "Cloud Control Plane não está vinculada" in response.json()["detail"]


def test_tailscale_setup_blocked_when_cloud_disconnected(auth_client, sample_container, db):
    # Cloud registrada, mas desconectada
    settings = AgentSettings(
        environment_token_encrypted=crypto.encrypt("env-secret-token"),
        cloud_environment_id="env_test_123",
    )
    db.add(settings)
    db.commit()

    with patch("app.cloud.websocket_client.CloudWebSocketClient.is_connected", new_callable=PropertyMock, return_value=False):
        response = auth_client.post(f"/api/containers/{sample_container.id}/tailscale/setup")
        assert response.status_code == 400
        assert "Cloud Control Plane está desconectada" in response.json()["detail"]


def test_tailscale_setup_allowed_when_cloud_connected(auth_client, sample_container, db):
    # Cloud registrada e conectada
    settings = AgentSettings(
        environment_token_encrypted=crypto.encrypt("env-secret-token"),
        cloud_environment_id="env_test_123",
    )
    db.add(settings)
    db.commit()

    with patch("app.cloud.websocket_client.CloudWebSocketClient.is_connected", new_callable=PropertyMock, return_value=True):
        # Mock do tailscale manager para não tentar invocar comandos Proxmox reais em background
        with patch("app.core.dependencies.get_tailscale_manager") as mock_factory:
            mock_manager = MagicMock()
            mock_factory.return_value = lambda c_id, c_num: mock_manager

            response = auth_client.post(f"/api/containers/{sample_container.id}/tailscale/setup")
            assert response.status_code == 202
            assert "job_id" in response.json()


def test_proxmox_permission_denied_exception_handler(auth_client, sample_container):
    # Simula erro de privilégio ProxmoxPermissionError lançado pelo service
    with patch("app.services.container_service.ContainerService.start") as mock_start:
        mock_start.side_effect = ProxmoxPermissionError(
            message="403 Forbidden: permission check failed",
            required_permission="Sys.Audit",
            path="/nodes/pve",
        )

        response = auth_client.post(f"/api/containers/{sample_container.id}/start")
        assert response.status_code == 403
        data = response.json()
        assert data["error_code"] == "PROXMOX_PERMISSION_DENIED"
        assert data["required_permission"] == "Sys.Audit"
        assert data["path"] == "/nodes/pve"
        assert "Permissão insuficiente" in data["detail"]
