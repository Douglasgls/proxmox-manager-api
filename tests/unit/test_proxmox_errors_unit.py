import pytest
from unittest.mock import MagicMock
from app.integrations.proxmox.exceptions import (
    ProxmoxPermissionError,
    ContainerNotFoundError,
    ProxmoxConnectionError,
    ProxmoxAPIError,
)
from app.integrations.proxmox.proxmox_client import ProxmoxClient


def test_proxmox_permission_error_properties():
    err = ProxmoxPermissionError(
        message="403 Forbidden: permission check failed",
        required_permission="Sys.Audit",
        path="/nodes/pve",
    )

    assert err.status_code == 403
    assert err.required_permission == "Sys.Audit"
    assert err.path == "/nodes/pve"
    assert "403 Forbidden" in err.message


def test_proxmox_client_api_error_detects_403_and_maps_permission():
    client = ProxmoxClient(host="192.168.0.10", user="test@pve", token_name="token", token_value="secret")

    # Simula mensagem padrão do Proxmoxer ao rejeitar com 403
    mock_ex = Exception("403 Forbidden: Permission check failed (/nodes/pve, Sys.Audit)")
    mock_ex.status_code = 403

    mapped_err = client._api_error(mock_ex)

    assert isinstance(mapped_err, ProxmoxPermissionError)
    assert mapped_err.status_code == 403
    assert mapped_err.path == "/nodes/pve"
    assert mapped_err.required_permission == "Sys.Audit"


def test_proxmox_client_is_not_found():
    client = ProxmoxClient(host="192.168.0.10", user="test@pve", token_name="token", token_value="secret")
    
    mock_404 = Exception("Not Found")
    mock_404.status_code = 404

    assert client._is_not_found(mock_404) is True

    mock_500 = Exception("Internal Server Error")
    mock_500.status_code = 500
    assert client._is_not_found(mock_500) is False
