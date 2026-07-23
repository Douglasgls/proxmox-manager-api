import unittest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from pydantic import ValidationError

from app.cloud.dto import CloudMessage, ContainerProvisionPayloadDTO, PublishedTailscaleNodeSnapshotDTO
from app.cloud.handlers.container_provision import ContainerProvisionHandler
from app.cloud.container_provision_service import (
    ContainerProvisionService,
    ContainerNotFoundError,
    ContainerNotPublishedError,
    ContainerNotRunningError,
)
from app.core.event_bus import internal_event_bus, ContainerProvisionCompleted
from app.models.container import Container
from app.tailscale.domain import TailscaleProvisionParams
from app.tailscale.model import TailscaleNode
from app.tailscale.service import mask_auth_key, TailscaleCommandError
from app.tailscale.provision_service import (
    TailscaleProvisionService,
    TailscaleNotInstalledError,
    TailscaleServiceNotRunningError,
    TailscaleNodeNotFoundError,
)


class TestContainerProvisionPayloadDTO(unittest.TestCase):

    def test_valid_payload(self):
        data = {
            "request_id": "req-123",
            "environment_id": "env-456",
            "container_id": "cont-789",
            "login_server": "https://headscale.example.com",
            "auth_key": "tskey-auth-1234567890abcdef",
            "hostname": "node-101",
        }
        dto = ContainerProvisionPayloadDTO.model_validate(data)
        self.assertEqual(dto.request_id, "req-123")
        self.assertEqual(dto.environment_id, "env-456")
        self.assertEqual(dto.container_id, "cont-789")
        self.assertEqual(dto.login_server, "https://headscale.example.com")
        self.assertEqual(dto.auth_key, "tskey-auth-1234567890abcdef")
        self.assertEqual(dto.hostname, "node-101")

    def test_cloud_payload_aliases(self):
        data = {
            "published_container_id": "917ab690-fb08-4370-97af-107708541ebc",
            "api_local_container_id": "400a8b61-53ed-4591-8c1b-d638fd39acac",
            "container_number": 100,
            "preauth_key": "hskey-auth-plHj4V-PNKMG-WTnbSOt6daRu4vI7EqQLoK5kPWebD9ZkQHMoZ-UZNpSfQ-22lGk7-KrqTrNJvSYP",
            "headscale_url": "http://localhost:8080",
            "headscale_user": "env_cb39d4a9-3bca-42b8-8908-a1503aaa53a7"
        }
        dto = ContainerProvisionPayloadDTO.model_validate(data)
        self.assertEqual(dto.container_id, "400a8b61-53ed-4591-8c1b-d638fd39acac")
        self.assertEqual(dto.login_server, "http://localhost:8080")
        self.assertEqual(dto.auth_key, "hskey-auth-plHj4V-PNKMG-WTnbSOt6daRu4vI7EqQLoK5kPWebD9ZkQHMoZ-UZNpSfQ-22lGk7-KrqTrNJvSYP")
        self.assertEqual(dto.container_number, 100)


    def test_invalid_payload_missing_fields(self):
        data = {
            "request_id": "req-123",
            "container_id": "cont-789",
        }
        with self.assertRaises(ValidationError):
            ContainerProvisionPayloadDTO.model_validate(data)


class TestAuthKeyMasking(unittest.TestCase):

    def test_mask_auth_key(self):
        key = "tskey-auth-1234567890abcdef"
        masked = mask_auth_key(key)
        self.assertEqual(masked, "tskey-auth-1************")
        self.assertNotIn("34567890abcdef", masked)


    def test_mask_short_auth_key(self):
        key = "shortkey"
        masked = mask_auth_key(key)
        self.assertEqual(masked, "shor************")


class TestTailscaleNodeModelProperties(unittest.TestCase):

    def test_node_snapshot_properties(self):
        node = TailscaleNode(
            container_id="c1",
            proxmox_container_id=100,
            installed=True,
            service_running=True,
            status_json={
                "Self": {
                    "Online": True,
                    "HostName": "my-host",
                    "DNSName": "my-host.example.com.",
                    "LastSeen": "2026-07-22T19:00:00Z",
                    "AdvertisedRoutes": ["10.0.0.0/24"],
                }
            },
        )
        self.assertTrue(node.online)
        self.assertEqual(node.hostname, "my-host")
        self.assertEqual(node.dns_name, "my-host.example.com.")
        self.assertEqual(node.last_seen, "2026-07-22T19:00:00Z")
        self.assertEqual(node.advertised_routes, ["10.0.0.0/24"])


class TestTailscaleProvisionService(unittest.TestCase):

    def setUp(self):
        self.db = MagicMock()
        self.proxmox_client = MagicMock()
        self.service = TailscaleProvisionService(
            db=self.db,
            proxmox_client=self.proxmox_client,
        )

    def test_provision_fails_when_node_not_found(self):
        self.service.repository.get_by_container_id = MagicMock(return_value=None)
        params = TailscaleProvisionParams(
            login_server="https://login.com",
            auth_key="tskey-auth-secret",
            hostname="host1",
        )
        with self.assertRaises(TailscaleNodeNotFoundError):
            self.service.provision("c1", 100, params, "req-1")

    @patch("app.tailscale.provision_service.TailscaleService")
    def test_provision_fails_when_not_installed(self, mock_ts_service_cls):
        mock_node = MagicMock(spec=TailscaleNode)
        self.service.repository.get_by_container_id = MagicMock(return_value=mock_node)

        mock_ts_instance = MagicMock()
        mock_ts_instance.is_installed.return_value = False
        mock_ts_service_cls.return_value = mock_ts_instance

        params = TailscaleProvisionParams(
            login_server="https://login.com",
            auth_key="tskey-auth-secret",
            hostname="host1",
        )
        with self.assertRaises(TailscaleNotInstalledError):
            self.service.provision("c1", 100, params, "req-1")

    @patch("app.tailscale.provision_service.TailscaleService")
    def test_provision_fails_when_service_not_running(self, mock_ts_service_cls):
        mock_node = MagicMock(spec=TailscaleNode)
        self.service.repository.get_by_container_id = MagicMock(return_value=mock_node)

        mock_ts_instance = MagicMock()
        mock_ts_instance.is_installed.return_value = True
        mock_ts_instance.is_service_running.return_value = False
        mock_ts_service_cls.return_value = mock_ts_instance

        params = TailscaleProvisionParams(
            login_server="https://login.com",
            auth_key="tskey-auth-secret",
            hostname="host1",
        )
        with self.assertRaises(TailscaleServiceNotRunningError):
            self.service.provision("c1", 100, params, "req-1")

    @patch("app.tailscale.provision_service.TailscaleService")
    def test_provision_success(self, mock_ts_service_cls):
        mock_node = MagicMock(spec=TailscaleNode)
        self.service.repository.get_by_container_id = MagicMock(return_value=mock_node)
        self.service.repository.update = MagicMock(return_value=mock_node)

        mock_ts_instance = MagicMock()
        mock_ts_instance.is_installed.return_value = True
        mock_ts_instance.is_service_running.return_value = True
        mock_ts_instance.get_version.return_value = "1.70.0"
        mock_ts_instance.get_machine_id.return_value = "mid-123"
        mock_ts_instance.get_node_key.return_value = "nodekey:456"
        mock_ts_instance.get_ip.return_value = "100.64.0.1"
        mock_ts_instance.get_status_json.return_value = {"Self": {"Online": True}}
        mock_ts_service_cls.return_value = mock_ts_instance

        params = TailscaleProvisionParams(
            login_server="https://login.com",
            auth_key="tskey-auth-secret",
            hostname="host1",
        )

        updated = self.service.provision("c1", 100, params, "req-1")

        mock_ts_instance.exec_tailscale_up.assert_called_once_with(params)
        self.assertEqual(updated.installed, True)
        self.assertEqual(updated.service_running, True)
        self.assertEqual(updated.version, "1.70.0")
        self.assertEqual(updated.machine_id, "mid-123")
        self.assertEqual(updated.node_key, "nodekey:456")
        self.assertEqual(updated.tailscale_ip, "100.64.0.1")


class TestContainerProvisionService(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.db = MagicMock()
        self.ts_provision_service = MagicMock()
        self.service = ContainerProvisionService(
            db=self.db,
            tailscale_provision_service=self.ts_provision_service,
        )

    async def test_container_not_found(self):
        self.service.container_repo.get = MagicMock(return_value=None)
        payload = ContainerProvisionPayloadDTO(
            request_id="req-1",
            environment_id="env-1",
            container_id="c-missing",
            login_server="https://srv.com",
            auth_key="tskey-auth-key",
            hostname="host1",
        )
        with self.assertRaises(ContainerNotFoundError):
            await self.service.provision_container(payload)

    async def test_container_not_published(self):
        container = MagicMock(spec=Container)
        container.id = "c1"
        container.tailscale_node = None
        self.service.container_repo.get = MagicMock(return_value=container)

        payload = ContainerProvisionPayloadDTO(
            request_id="req-1",
            environment_id="env-1",
            container_id="c1",
            login_server="https://srv.com",
            auth_key="tskey-auth-key",
            hostname="host1",
        )
        with self.assertRaises(ContainerNotPublishedError):
            await self.service.provision_container(payload)

    async def test_container_not_running(self):
        container = MagicMock(spec=Container)
        container.id = "c1"
        container.status = "stopped"
        container.tailscale_node = MagicMock(spec=TailscaleNode)
        self.service.container_repo.get = MagicMock(return_value=container)

        payload = ContainerProvisionPayloadDTO(
            request_id="req-1",
            environment_id="env-1",
            container_id="c1",
            login_server="https://srv.com",
            auth_key="tskey-auth-key",
            hostname="host1",
        )
        with self.assertRaises(ContainerNotRunningError):
            await self.service.provision_container(payload)

    async def test_provision_container_success_emits_event(self):
        container = MagicMock(spec=Container)
        container.id = "c1"
        container.container_number = 101
        container.status = "running"
        container.tailscale_node = MagicMock(spec=TailscaleNode)
        self.service.container_repo.get = MagicMock(return_value=container)

        received_events = []
        def on_event(event):
            received_events.append(event)

        internal_event_bus.subscribe(ContainerProvisionCompleted, on_event)

        payload = ContainerProvisionPayloadDTO(
            request_id="req-1",
            environment_id="env-1",
            container_id="c1",
            login_server="https://srv.com",
            auth_key="tskey-auth-key",
            hostname="host1",
        )

        await self.service.provision_container(payload)

        self.ts_provision_service.provision.assert_called_once()
        self.assertEqual(len(received_events), 1)
        self.assertIsInstance(received_events[0], ContainerProvisionCompleted)
        self.assertEqual(received_events[0].container_id, "c1")
        self.assertEqual(received_events[0].request_id, "req-1")


class TestContainerProvisionHandler(unittest.IsolatedAsyncioTestCase):

    async def test_handle_provision_invalid_payload(self):
        send_mock = AsyncMock()
        msg = CloudMessage(
            request_id="req-invalid",
            type="container.provision",
            payload={"invalid": "data"},
        )
        await ContainerProvisionHandler.handle_provision(msg, send_mock)

        send_mock.assert_called_once()
        sent_arg = send_mock.call_args[0][0]
        data = json.loads(sent_arg)
        self.assertFalse(data["success"])
        self.assertEqual(data["error"]["code"], "INVALID_PAYLOAD")

    @patch("app.cloud.handlers.container_provision.ContainerProvisionService")
    async def test_handle_provision_success(self, mock_service_cls):
        send_mock = AsyncMock()
        mock_service_inst = MagicMock()
        mock_service_inst.provision_container = AsyncMock()
        mock_service_cls.return_value = mock_service_inst

        msg = CloudMessage(
            request_id="req-99",
            type="container.provision",
            payload={
                "environment_id": "env-1",
                "container_id": "c-99",
                "login_server": "https://headscale.srv",
                "auth_key": "tskey-auth-test",
                "hostname": "host-99",
            },
        )
        await ContainerProvisionHandler.handle_provision(msg, send_mock)

        send_mock.assert_called_once()
        sent_arg = send_mock.call_args[0][0]
        data = json.loads(sent_arg)
        self.assertTrue(data["success"])
        self.assertEqual(data["payload"]["status"], "SUCCESS")
        self.assertEqual(data["payload"]["container_id"], "c-99")


if __name__ == "__main__":
    unittest.main()
