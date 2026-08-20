import unittest
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.container import Container
from app.models.client_connection import ClientConnection
from app.cloud.models import AgentSettings
from app.cloud.dto import CloudMessage, NodeSyncEventDataDTO
from app.cloud.handlers.node_sync import NodeSyncHandler
from app.services.environment_state_sync_service import EnvironmentStateSyncService
from unittest.mock import patch


class TestClientConnections(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()
        self.db.execute(text("PRAGMA foreign_keys = ON;"))


        # Configurar AgentSettings para passar na validação de contexto
        settings = AgentSettings(
            id=1,
            cloud_environment_id="ENV_TEST_123",
            environment_token_encrypted=b"secret",
        )
        self.db.add(settings)

        # Configurar Container de teste
        self.container = Container(
            id="ct-uuid-101",
            container_number=101,
            name="app-container-101",
            password="secretpassword",
            status="running",
            cpu=2,
            memory_mb=2048,
        )

        self.db.add(self.container)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    async def test_client_connection_creation(self):
        """Testa criação de ClientConnection via delta de evento da Cloud."""
        sent = []
        async def mock_send(msg: str):
            sent.append(msg)

        msg = CloudMessage(
            request_id="req-client-1",
            type="node.status_changed",
            version=1,
            payload={
                "environment_id": "ENV_TEST_123",
                "deltas": [
                    {
                        "action": "NODE_CREATED",
                        "node_id": "cloud-conn-999",
                        "headscale_node_id": "15",
                        "hostname": "notebook-user",
                        "online": True,
                        "tailscale_ip": "100.64.0.15"
                    }
                ]
            }
        )

        with patch("app.cloud.handlers.node_sync.SessionLocal", return_value=self.db):
            await NodeSyncHandler.handle_node_event(msg, mock_send)

        conn = self.db.query(ClientConnection).filter(ClientConnection.headscale_node_id == "15").first()
        self.assertIsNotNone(conn)
        self.assertEqual(conn.hostname, "notebook-user")
        self.assertEqual(conn.tailscale_ip, "100.64.0.15")
        self.assertTrue(conn.online)
        self.assertEqual(conn.status, "ACTIVE")

    async def test_cascade_delete_container_removes_client_connections(self):
        """Testa se a exclusão do Container remove em cascata (CASCADE) suas ClientConnections."""
        conn = ClientConnection(
            id="conn-uuid-100",
            cloud_connection_id="cloud-conn-100",
            headscale_node_id="20",
            container_id=self.container.id,
            hostname="device-linked",
            tailscale_ip="100.64.0.20",
            online=True,
            status="ACTIVE",
        )
        self.db.add(conn)
        self.db.commit()

        # Verificar se a conexão está presente
        found = self.db.query(ClientConnection).filter(ClientConnection.id == "conn-uuid-100").first()
        self.assertIsNotNone(found)

        # Deletar o Container
        self.db.delete(self.container)
        self.db.commit()

        # Verificar se a ClientConnection foi removida via CASCADE
        found_after = self.db.query(ClientConnection).filter(ClientConnection.id == "conn-uuid-100").first()
        self.assertIsNone(found_after)

    async def test_client_connection_status_update(self):
        """Testa atualização incremental de status da conexão (online/offline)."""
        sync_service = EnvironmentStateSyncService(self.db)

        # Criar registro inicial
        dto_online = NodeSyncEventDataDTO(
            node_id="cloud-conn-300",
            headscale_node_id="30",
            hostname="mobile-client",
            tailscale_ip="100.64.0.30",
            online=True,
        )
        res_online = sync_service.upsert_node_state(dto_online)
        self.assertIsInstance(res_online, ClientConnection)
        self.assertTrue(res_online.online)
        self.assertEqual(res_online.status, "ACTIVE")

        # Atualizar para offline
        dto_offline = NodeSyncEventDataDTO(
            node_id="cloud-conn-300",
            headscale_node_id="30",
            online=False,
        )
        res_offline = sync_service.upsert_node_state(dto_offline)
        self.assertIsInstance(res_offline, ClientConnection)
        self.assertFalse(res_offline.online)
        self.assertEqual(res_offline.status, "DISCONNECTED")

    async def test_client_connection_removal_event(self):
        """Testa se o evento node.removed remove a ClientConnection do banco."""
        sync_service = EnvironmentStateSyncService(self.db)

        dto = NodeSyncEventDataDTO(
            node_id="cloud-conn-400",
            headscale_node_id="40",
            hostname="to-remove-device",
            tailscale_ip="100.64.0.40",
            online=True,
        )
        sync_service.upsert_node_state(dto)

        # Remover
        removed = sync_service.remove_node_state(dto)
        self.assertTrue(removed)

        found = self.db.query(ClientConnection).filter(ClientConnection.headscale_node_id == "40").first()
        self.assertIsNone(found)


if __name__ == "__main__":
    unittest.main()
