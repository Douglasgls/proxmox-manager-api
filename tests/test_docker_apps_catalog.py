import unittest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.models.base import Base
from app.models.component import ComponentCategory
from app.repositories.component_repository import ComponentRepository
from app.services.component_service import ComponentService
from app.components.registry import ComponentRegistry
from app.components.uptime_kuma_component import UptimeKumaComponent
from app.components.postgresql_component import PostgresqlComponent
from app.components.redis_component import RedisComponent
from app.components.mariadb_component import MariadbComponent
from app.components.jellyfin_component import JellyfinComponent
from app.components.filegator_component import FileGatorComponent
from app.main import app
from app.security.dependencies import get_current_user
from app.core.dependencies import get_db
from app.models.user import User


class TestDockerAppsCatalog(unittest.TestCase):

    def test_uptime_kuma_component(self):
        kuma = UptimeKumaComponent(config={"host_port": 3001})
        self.assertEqual(kuma.slug, "uptime-kuma")
        self.assertEqual(kuma.name, "Uptime Kuma")
        self.assertEqual(kuma.container_port, 3001)
        self.assertEqual(kuma.host_port, 3001)
        self.assertTrue(kuma.is_web_app)
        self.assertEqual(kuma.protocol, "http")
        self.assertEqual(kuma.volumes, ["uptime-kuma-data:/app/data"])

        plan = kuma.get_plan()
        step = plan.steps[0]
        self.assertIn("-p 0.0.0.0:3001:3001", step.install_commands[1])
        self.assertIn("-v uptime-kuma-data:/app/data", step.install_commands[1])
        self.assertIn("louislam/uptime-kuma:1", step.install_commands[1])

    def test_postgresql_component_requires_password(self):
        # Sem POSTGRES_PASSWORD deve falhar
        pg_invalid = PostgresqlComponent(config={"host_port": 5432})
        with self.assertRaises(ValueError) as ctx:
            pg_invalid.get_plan()
        self.assertIn("POSTGRES_PASSWORD", str(ctx.exception))

        # Com POSTGRES_PASSWORD deve gerar o plano corretamente
        pg_valid = PostgresqlComponent(config={
            "host_port": 5432,
            "env": {"POSTGRES_PASSWORD": "secretpassword", "POSTGRES_DB": "my_app_db"}
        })
        self.assertEqual(pg_valid.container_port, 5432)
        self.assertFalse(pg_valid.is_web_app)
        self.assertEqual(pg_valid.protocol, "tcp")
        self.assertEqual(pg_valid.volumes, ["postgres-data:/var/lib/postgresql/data"])

        plan = pg_valid.get_plan()
        step = plan.steps[0]
        self.assertIn("-p 0.0.0.0:5432:5432", step.install_commands[1])
        self.assertIn("-e POSTGRES_PASSWORD=\"secretpassword\"", step.install_commands[1])
        self.assertIn("-e POSTGRES_DB=\"my_app_db\"", step.install_commands[1])
        self.assertIn("-v postgres-data:/var/lib/postgresql/data", step.install_commands[1])

    def test_redis_component(self):
        redis = RedisComponent(config={
            "host_port": 6379,
            "env": {"REDIS_PASSWORD": "redispassword"}
        })
        self.assertEqual(redis.slug, "redis")
        self.assertEqual(redis.container_port, 6379)
        self.assertFalse(redis.is_web_app)
        self.assertEqual(redis.protocol, "tcp")
        self.assertEqual(redis.volumes, ["redis-data:/data"])

        plan = redis.get_plan()
        step = plan.steps[0]
        self.assertIn("-p 0.0.0.0:6379:6379", step.install_commands[1])
        self.assertIn("-e REDIS_PASSWORD=\"redispassword\"", step.install_commands[1])
        self.assertIn("-v redis-data:/data", step.install_commands[1])

    def test_mariadb_component_requires_password(self):
        mariadb_invalid = MariadbComponent(config={"host_port": 3306})
        with self.assertRaises(ValueError) as ctx:
            mariadb_invalid.get_plan()
        self.assertIn("MARIADB_ROOT_PASSWORD", str(ctx.exception))

        mariadb_valid = MariadbComponent(config={
            "host_port": 3306,
            "env": {"MARIADB_ROOT_PASSWORD": "rootpassword123"}
        })
        self.assertEqual(mariadb_valid.container_port, 3306)
        self.assertFalse(mariadb_valid.is_web_app)
        self.assertEqual(mariadb_valid.protocol, "tcp")

        plan = mariadb_valid.get_plan()
        step = plan.steps[0]
        self.assertIn("-p 0.0.0.0:3306:3306", step.install_commands[1])
        self.assertIn("-e MARIADB_ROOT_PASSWORD=\"rootpassword123\"", step.install_commands[1])
        self.assertIn("-v mariadb-data:/var/lib/mysql", step.install_commands[1])

    def test_jellyfin_component_ports_and_volumes(self):
        jellyfin = JellyfinComponent(config={"host_port": 8096})
        self.assertEqual(jellyfin.slug, "jellyfin")
        self.assertEqual(jellyfin.container_port, 8096)
        self.assertEqual(jellyfin.host_port, 8096)
        self.assertEqual(jellyfin.extra_ports, ["7359:7359/udp"])
        self.assertTrue(jellyfin.is_web_app)
        self.assertEqual(len(jellyfin.volumes), 3)
        self.assertIn("jellyfin-config:/config", jellyfin.volumes)
        self.assertIn("jellyfin-cache:/cache", jellyfin.volumes)
        self.assertIn("jellyfin-media:/media", jellyfin.volumes)

        plan = jellyfin.get_plan()
        step = plan.steps[0]
        self.assertIn("-p 0.0.0.0:8096:8096", step.install_commands[1])
        self.assertIn("-p 7359:7359/udp", step.install_commands[1])
        self.assertIn("-v jellyfin-config:/config", step.install_commands[1])
        self.assertIn("-v jellyfin-cache:/cache", step.install_commands[1])
        self.assertIn("-v jellyfin-media:/media", step.install_commands[1])

    def test_container_port_override(self):
        # Override de porta interna em configurações avançadas
        pg_override = PostgresqlComponent(config={
            "host_port": 5433,
            "container_port": 5439,
            "env": {"POSTGRES_PASSWORD": "secretpassword"}
        })
        self.assertEqual(pg_override.host_port, 5433)
        self.assertEqual(pg_override.container_port, 5439)
        plan = pg_override.get_plan()
        step = plan.steps[0]
        self.assertIn("-p 0.0.0.0:5433:5439", step.install_commands[1])


class TestDockerAppsAPIAndSync(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

        self.service = ComponentService(ComponentRepository(self.db))
        self.service.sync_default_catalog()

        mock_user = MagicMock(spec=User)
        mock_user.id = "user-123"
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: self.db

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_sync_default_catalog_populates_all_docker_apps(self):
        docker_apps = self.service.list_components(category=ComponentCategory.DOCKER_APPS.value)
        slugs = [c.slug for c in docker_apps]

        self.assertIn("filegator", slugs)
        self.assertIn("uptime-kuma", slugs)
        self.assertIn("postgresql", slugs)
        self.assertIn("redis", slugs)
        self.assertIn("mariadb", slugs)
        self.assertIn("jellyfin", slugs)

    def test_get_components_api_returns_metadata(self):
        response = self.client.get("/components?category=docker_apps")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertGreaterEqual(len(data), 6)

        kuma_item = next((item for item in data if item["slug"] == "uptime-kuma"), None)
        self.assertIsNotNone(kuma_item)
        self.assertIsNotNone(kuma_item["metadata"])
        self.assertEqual(kuma_item["metadata"]["default_config"]["container_port"], 3001)
        self.assertTrue(kuma_item["metadata"]["is_web_app"])

        pg_item = next((item for item in data if item["slug"] == "postgresql"), None)
        self.assertIsNotNone(pg_item)
        self.assertIsNotNone(pg_item["metadata"])
        self.assertEqual(pg_item["metadata"]["default_config"]["container_port"], 5432)
        self.assertFalse(pg_item["metadata"]["is_web_app"])

        env_schemas = pg_item["metadata"]["env_vars_schema"]
        pg_pass_schema = next((s for s in env_schemas if s["name"] == "POSTGRES_PASSWORD"), None)
        self.assertIsNotNone(pg_pass_schema)
        self.assertTrue(pg_pass_schema["required"])


if __name__ == "__main__":
    unittest.main()
