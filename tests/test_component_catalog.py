import unittest
from unittest.mock import MagicMock
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.models.base import Base
from app.models.component import Component, ComponentCategory
from app.repositories.component_repository import ComponentRepository
from app.services.component_service import ComponentService
from app.components.registry import ComponentRegistry
from app.components.base_components import BaseComponent
from app.components.native_component import NativeComponent
from app.components.docker_application_component import DockerApplicationComponent
from app.components.curl_component import CurlComponent
from app.components.git_component import GitComponent
from app.components.tailscale_component import TailscaleComponent
from app.components.game_component import GameComponent
from app.components.programming.python import PythonComponent
from app.provision.plan import ProvisionPlan
from app.provision.step import ProvisionStep
from app.provision.engine import ProvisionEngine
from app.integrations.proxmox.container_session import ContainerSession
from app.integrations.proxmox.models import CommandResult

from app.main import app
from app.security.dependencies import get_current_user
from app.models.user import User


class TestComponentHierarchyAndDeclarations(unittest.TestCase):

    def test_class_hierarchy(self):
        curl = CurlComponent()
        git = GitComponent()
        tailscale = TailscaleComponent()
        py = PythonComponent()
        game = GameComponent()

        self.assertIsInstance(curl, NativeComponent)
        self.assertIsInstance(curl, BaseComponent)
        self.assertEqual(curl.category, ComponentCategory.NATIVE.value)

        self.assertIsInstance(git, NativeComponent)
        self.assertEqual(git.category, ComponentCategory.NATIVE.value)

        self.assertIsInstance(tailscale, NativeComponent)
        self.assertEqual(tailscale.category, ComponentCategory.NATIVE.value)

        self.assertIsInstance(py, NativeComponent)
        self.assertEqual(py.category, ComponentCategory.NATIVE.value)

        self.assertIsInstance(game, DockerApplicationComponent)
        self.assertIsInstance(game, BaseComponent)
        self.assertEqual(game.category, ComponentCategory.DOCKER_APPLICATION.value)

    def test_game_declarative_get_plan(self):
        game = GameComponent()
        plan = game.get_plan()
        self.assertIsInstance(plan, ProvisionPlan)
        self.assertEqual(len(plan.steps), 1)

        step = plan.steps[0]
        self.assertEqual(step.component_name, "game")
        # Deve ter comandos de instalação do Docker + idempotência do app
        self.assertEqual(len(step.install_commands), 2)
        self.assertIn("command -v docker", step.install_commands[0])
        self.assertIn("sithum/game", step.install_commands[1])
        self.assertIn("80:80", step.install_commands[1])

        # Deve ter comandos de validação do Docker e da aplicação (sem dependência de curl)
        self.assertEqual(len(step.validation_commands), 2)
        self.assertIn("docker info", step.validation_commands[0])
        self.assertIn("docker inspect", step.validation_commands[1])
        self.assertNotIn("curl", step.validation_commands[1])


class TestComponentRegistry(unittest.TestCase):

    def test_resolve_registered_slugs(self):
        self.assertIsInstance(ComponentRegistry.get("curl"), CurlComponent)
        self.assertIsInstance(ComponentRegistry.get("git"), GitComponent)
        self.assertIsInstance(ComponentRegistry.get("tailscale"), TailscaleComponent)
        self.assertIsInstance(ComponentRegistry.get("game"), GameComponent)
        self.assertIsInstance(ComponentRegistry.get("python"), PythonComponent)

    def test_unregistered_slug_raises_error(self):
        with self.assertRaises(ValueError):
            ComponentRegistry.get("unregistered_invalid_slug")


class TestComponentServiceAndRepository(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        self.repository = ComponentRepository(self.db)
        self.service = ComponentService(self.repository)

    def tearDown(self):
        self.db.close()

    def test_sync_default_catalog_is_idempotent(self):
        # Primeira sincronização
        synced_1 = self.service.sync_default_catalog()
        self.assertEqual(len(synced_1), 4)

        slugs = [c.slug for c in self.service.list_components()]
        self.assertIn("curl", slugs)
        self.assertIn("git", slugs)
        self.assertIn("tailscale", slugs)
        self.assertIn("game", slugs)
        self.assertNotIn("python", slugs)  # Python mantido no código, mas fora do catálogo default ativo

        # Segunda sincronização (idempotente)
        synced_2 = self.service.sync_default_catalog()
        self.assertEqual(len(synced_2), 4)

        total_in_db = self.repository.list_all()
        self.assertEqual(len(total_in_db), 4)

    def test_list_by_category(self):
        self.service.sync_default_catalog()
        native_components = self.service.list_components(category="native")
        self.assertEqual(len(native_components), 3)

        docker_components = self.service.list_components(category="docker_application")
        self.assertEqual(len(docker_components), 1)
        self.assertEqual(docker_components[0].slug, "game")


class TestComponentsAPI(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Seed catalog
        service = ComponentService(ComponentRepository(self.db))
        service.sync_default_catalog()

        mock_user = MagicMock(spec=User)
        mock_user.id = "user-123"
        app.dependency_overrides[get_current_user] = lambda: mock_user

        from app.core.dependencies import get_db
        app.dependency_overrides[get_db] = lambda: self.db

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_get_components_list(self):
        response = self.client.get("/components")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 4)

    def test_get_components_by_category(self):
        response = self.client.get("/components?category=docker_application")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["slug"], "game")

    def test_get_component_by_slug(self):
        response = self.client.get("/components/game")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["slug"], "game")
        self.assertEqual(data["category"], "docker_application")


if __name__ == "__main__":
    unittest.main()
