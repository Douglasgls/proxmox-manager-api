import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.container import Container
from app.models.component import Component
from app.models.container_component import ContainerComponent
from app.tailscale.model import TailscaleNode
from app.cloud.published_container_service import PublishedContainerService


class TestPublishedContainerService(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_published_container_mapping(self):
        # 1. Criar container e nó Tailscale
        container = Container(
            id="ct-uuid-1",
            container_number=200,
            name="Meu App API",
            password="secretpassword",
            status="running",
        )
        self.db.add(container)
        self.db.commit()

        ts_node = TailscaleNode(
            id=1,
            container_id=container.id,
            proxmox_container_id=200,
            installed=True,
            service_running=True,
            tailscale_ip="100.64.0.15",
            status_json={"Self": {"HostName": "meu-app-api", "Online": True}},
        )
        self.db.add(ts_node)
        self.db.commit()

        service = PublishedContainerService(self.db)
        snapshots = service.get_published_containers()

        self.assertEqual(len(snapshots), 1)
        snap = snapshots[0]
        self.assertEqual(snap.name, "Meu App API")
        self.assertEqual(snap.hostname, "meu-app-api")
        self.assertEqual(snap.dns_name, "meu-app-api.interno")

        # Verificar se o Tailscale snapshot contem as novas propriedades
        self.assertIsNotNone(snap.tailscale)
        self.assertEqual(snap.tailscale.hostname, "meu-app-api")
        self.assertEqual(snap.tailscale.dns_name, "meu-app-api.interno")
        self.assertEqual(snap.tailscale.tailscale_ip, "100.64.0.15")

        # Como não possui componentes, porta padrão 80 é atribuída
        self.assertEqual(len(snap.ports), 1)
        self.assertEqual(snap.ports[0].port, 80)
        self.assertEqual(snap.ports[0].protocol, "tcp")

    def test_port_extraction_from_components(self):
        # 1. Criar container com dois componentes (PostgreSQL e Redis)
        container = Container(
            id="ct-uuid-2",
            container_number=201,
            name="Database Container",
            password="secretpassword",
            status="running",
        )
        self.db.add(container)
        self.db.commit()

        ts_node = TailscaleNode(
            id=2,
            container_id=container.id,
            proxmox_container_id=201,
            installed=True,
            service_running=True,
            tailscale_ip="100.64.0.16",
            status_json={"Self": {"HostName": "database-container", "Online": True}},
        )
        self.db.add(ts_node)

        comp_pg = Component(id="comp-1", name="PostgreSQL", slug="postgres", category="native")
        comp_redis = Component(id="comp-2", name="Redis", slug="redis", category="native")
        self.db.add_all([comp_pg, comp_redis])
        self.db.commit()

        cc1 = ContainerComponent(id="cc-1", container_id=container.id, component_id=comp_pg.id, status="INSTALLED")
        cc2 = ContainerComponent(id="cc-2", container_id=container.id, component_id=comp_redis.id, status="INSTALLED")
        self.db.add_all([cc1, cc2])
        self.db.commit()

        service = PublishedContainerService(self.db)
        snapshots = service.get_published_containers()

        self.assertEqual(len(snapshots), 1)
        snap = snapshots[0]
        self.assertEqual(snap.hostname, "database-container")
        self.assertEqual(snap.dns_name, "database-container.interno")

        # Portas extraídas devem ser 5432 (Postgres) e 6379 (Redis)
        extracted_ports = [p.port for p in snap.ports]
        self.assertIn(5432, extracted_ports)
        self.assertIn(6379, extracted_ports)


if __name__ == "__main__":
    unittest.main()
