import unittest
from unittest.mock import patch
import asyncio
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.container import Container
from app.cloud.models import AgentSettings
from app.tailscale.model import TailscaleNode
from app.cloud.dto import CloudMessage, NodeSyncEventDataDTO
from app.cloud.dispatcher import CloudDispatcher
from app.cloud.handlers.node_sync import NodeSyncHandler, _processed_events
from app.services.environment_state_sync_service import EnvironmentStateSyncService


class NodeStateSyncTestCase(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Configurar banco SQLite em memória isolado para testes
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Limpar cache de idempotência para garantir isolamento entre testes
        _processed_events.clear()

        # Criar AgentSettings base de teste
        self.settings = AgentSettings(
            id="local-agent-uuid",
            cloud_environment_id="ENV_TEST_123",
            environment_token_encrypted="encrypted-token",
            jwt="test-jwt-token",
        )
        self.db.add(self.settings)

        # Criar Container base de teste
        self.container = Container(
            id="container-uuid-1",
            container_number=101,
            name="test-ct-101",
            password="secretpassword",
            status="running",
            cloud_container_id="cloud-ct-101",
        )
        self.db.add(self.container)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_validate_context_success(self):
        """Teste 10a: Validação de contexto com environment_id correto."""
        service = EnvironmentStateSyncService(self.db)
        self.assertTrue(service.validate_context("ENV_TEST_123"))

    def test_validate_context_mismatch(self):
        """Teste 2a: Validação de contexto com environment_id divergente."""
        service = EnvironmentStateSyncService(self.db)
        self.assertFalse(service.validate_context("ENV_OTHER_999"))

    def test_upsert_node_created(self):
        """Teste 4: Evento node.created cria nó vinculado ao container local."""
        service = EnvironmentStateSyncService(self.db)
        dto = NodeSyncEventDataDTO(
            node_id="hs-node-001",
            machine_id="mid-001",
            tailscale_ip="100.64.0.10",
            online=True,
            hostname="test-ct-101",
            container_id=self.container.id,
            proxmox_container_id=101,
        )

        node = service.upsert_node_state(dto)
        self.assertIsNotNone(node)
        self.assertEqual(node.headscale_node_id, "hs-node-001")
        self.assertEqual(node.machine_id, "mid-001")
        self.assertEqual(node.tailscale_ip, "100.64.0.10")
        self.assertTrue(node.online)

    def test_upsert_node_updated_partial_patch(self):
        """Teste 5: Evento node.updated atualiza apenas campos enviados, preservando metadados."""
        service = EnvironmentStateSyncService(self.db)

        # Criar nó inicial
        initial_dto = NodeSyncEventDataDTO(
            node_id="hs-node-002",
            machine_id="mid-002",
            tailscale_ip="100.64.0.20",
            online=True,
            hostname="initial-hostname",
            container_id=self.container.id,
        )
        node = service.upsert_node_state(initial_dto)
        self.assertEqual(node.hostname, "initial-hostname")

        # Atualizar apenas o status online sem enviar hostname nem tailscale_ip
        delta_dto = NodeSyncEventDataDTO(
            node_id="hs-node-002",
            online=False,
        )
        updated_node = service.upsert_node_state(delta_dto)

        self.assertFalse(updated_node.online)
        self.assertEqual(updated_node.hostname, "initial-hostname")  # Preservado!
        self.assertEqual(updated_node.tailscale_ip, "100.64.0.20")  # Preservado!

    def test_online_offline_status_changed(self):
        """Teste 5 & 6: Transição de estado Online <-> Offline."""
        service = EnvironmentStateSyncService(self.db)
        dto = NodeSyncEventDataDTO(
            node_id="hs-node-003",
            online=True,
            container_id=self.container.id,
        )
        node = service.upsert_node_state(dto)
        self.assertTrue(node.online)

        # Mudar para offline
        dto_off = NodeSyncEventDataDTO(node_id="hs-node-003", online=False)
        node_off = service.upsert_node_state(dto_off)
        self.assertFalse(node_off.online)

        # Mudar para online
        dto_on = NodeSyncEventDataDTO(node_id="hs-node-003", online=True)
        node_on = service.upsert_node_state(dto_on)
        self.assertTrue(node_on.online)

    def test_node_removed(self):
        """Teste 7: node.removed deleta o TailscaleNode permitindo recreação limpa."""
        service = EnvironmentStateSyncService(self.db)
        dto = NodeSyncEventDataDTO(
            node_id="hs-node-del",
            container_id=self.container.id,
        )
        node = service.upsert_node_state(dto)
        self.assertIsNotNone(node)

        # Remover nó
        success = service.remove_node_state(dto)
        self.assertTrue(success)

        # Verificar se foi removido do banco
        found = self.db.query(TailscaleNode).filter(TailscaleNode.headscale_node_id == "hs-node-del").first()
        self.assertIsNone(found)

    def test_search_prioritization(self):
        """Teste 9: Prioridade na busca headscale_node_id -> machine_id -> tailscale_ip."""
        service = EnvironmentStateSyncService(self.db)
        dto = NodeSyncEventDataDTO(
            node_id="hs-pri-1",
            machine_id="m-pri-1",
            tailscale_ip="100.64.0.99",
            container_id=self.container.id,
        )
        service.upsert_node_state(dto)

        # Buscar com headscale_node_id diferente mas mesmo tailscale_ip -> deve encontrar por headscale_node_id prioritariamente se corresponder
        search_by_hs = service._find_node(NodeSyncEventDataDTO(node_id="hs-pri-1"))
        self.assertIsNotNone(search_by_hs)
        self.assertEqual(search_by_hs.headscale_node_id, "hs-pri-1")

        search_by_mid = service._find_node(NodeSyncEventDataDTO(machine_id="m-pri-1"))
        self.assertIsNotNone(search_by_mid)

        search_by_ip = service._find_node(NodeSyncEventDataDTO(tailscale_ip="100.64.0.99"))
        self.assertIsNotNone(search_by_ip)

    async def test_handler_valid_event(self):
        """Teste 1: Evento válido recebido pelo NodeSyncHandler."""
        sent_messages = []

        async def mock_send(msg: str):
            sent_messages.append(msg)

        msg = CloudMessage(
            event_id="evt-100",
            request_id="req-100",
            type="node.status_changed",
            version=1,
            environment_id="ENV_TEST_123",
            data={
                "node_id": "hs-node-h1",
                "online": True,
                "container_id": self.container.id,
            },
        )

        # Patch na fábrica de sessão para usar nosso DB de teste
        original_session = NodeSyncHandler
        with patch("app.cloud.handlers.node_sync.SessionLocal", return_value=self.db):
            await NodeSyncHandler.handle_node_event(msg, mock_send)

        self.assertEqual(len(sent_messages), 1)
        self.assertIn('"success":true', sent_messages[0])

    async def test_handler_mismatched_environment_rejected(self):
        """Teste 2: Evento com environment_id de outro ambiente é rejeitado."""
        sent_messages = []

        async def mock_send(msg: str):
            sent_messages.append(msg)

        msg = CloudMessage(
            event_id="evt-200",
            request_id="req-200",
            type="node.status_changed",
            version=1,
            environment_id="ENV_OTHER_999",  # Divergente!
            data={"node_id": "hs-node-h2", "online": True},
        )

        with patch("app.cloud.handlers.node_sync.SessionLocal", return_value=self.db):
            await NodeSyncHandler.handle_node_event(msg, mock_send)

        self.assertEqual(len(sent_messages), 1)
        self.assertIn('"code":"ENVIRONMENT_MISMATCH"', sent_messages[0])

    async def test_handler_idempotency_duplicate_event_ignored(self):
        """Teste 3: Evento duplicado com mesmo event_id é ignorado."""
        sent_messages = []

        async def mock_send(msg: str):
            sent_messages.append(msg)

        msg = CloudMessage(
            event_id="evt-dup-1",
            request_id="req-dup-1",
            type="node.status_changed",
            version=1,
            environment_id="ENV_TEST_123",
            data={"node_id": "hs-node-dup", "online": True, "container_id": self.container.id},
        )

        with patch("app.cloud.handlers.node_sync.SessionLocal", return_value=self.db):
            # Enviar primeira vez
            await NodeSyncHandler.handle_node_event(msg, mock_send)
            self.assertEqual(len(sent_messages), 1)

            # Enviar segunda vez com mesmo event_id
            await NodeSyncHandler.handle_node_event(msg, mock_send)
            self.assertEqual(len(sent_messages), 2)
            self.assertIn("SKIPPED_DUPLICATE", sent_messages[1])

    async def test_dispatcher_integration(self):
        """Teste 11: Integração com o CloudDispatcher."""
        dispatcher = CloudDispatcher()
        sent_messages = []

        async def mock_send(msg: str):
            sent_messages.append(msg)

        dispatcher.register("node.status_changed", NodeSyncHandler.handle_node_event)

        msg = CloudMessage(
            event_id="evt-disp-1",
            request_id="req-disp-1",
            type="node.status_changed",
            version=1,
            environment_id="ENV_TEST_123",
            data={"node_id": "hs-node-disp", "online": False, "container_id": self.container.id},
        )

        with patch("app.cloud.handlers.node_sync.SessionLocal", return_value=self.db):
            await dispatcher.dispatch(msg, mock_send)

        self.assertEqual(len(sent_messages), 1)

    async def test_handler_deltas_client_node(self):
        """Teste de recebimento de payload.deltas contendo cliente VPN externo sem container."""
        sent_messages = []

        async def mock_send(msg: str):
            sent_messages.append(msg)

        msg = CloudMessage(
            request_id="ab253276-e798-4f03-9499-f605d2ce0e35",
            type="node.status_changed",
            version=1,
            payload={
                "environment_id": "ENV_TEST_123",
                "deltas": [
                    {
                        "action": "NODE_CREATED",
                        "node_id": "3724618f-2c1b-47b1-9bc2-239534625dc1",
                        "headscale_node_id": "10",
                        "hostname": "client-teste",
                        "online": True,
                        "tailscale_ip": "100.64.0.5"
                    }
                ]
            }
        )

        with patch("app.cloud.handlers.node_sync.SessionLocal", return_value=self.db):
            await NodeSyncHandler.handle_node_event(msg, mock_send)

        from app.models.client_connection import ClientConnection
        found = self.db.query(ClientConnection).filter(ClientConnection.headscale_node_id == "10").first()
        self.assertIsNotNone(found)
        self.assertEqual(found.hostname, "client-teste")
        self.assertEqual(found.tailscale_ip, "100.64.0.5")
        self.assertTrue(found.online)
        self.assertIsNone(found.container_id)



if __name__ == "__main__":
    unittest.main()

