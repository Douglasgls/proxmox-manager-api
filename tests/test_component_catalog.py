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
from app.components.filegator_component import FileGatorComponent
from app.core.exceptions import DomainValidationError
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
        filegator = FileGatorComponent()

        self.assertIsInstance(curl, NativeComponent)
        self.assertIsInstance(curl, BaseComponent)
        self.assertEqual(curl.category, ComponentCategory.NATIVE.value)

        self.assertIsInstance(git, NativeComponent)
        self.assertEqual(git.category, ComponentCategory.NATIVE.value)

        self.assertIsInstance(tailscale, NativeComponent)
        self.assertEqual(tailscale.category, ComponentCategory.NATIVE.value)

        self.assertIsInstance(filegator, DockerApplicationComponent)
        self.assertIsInstance(filegator, BaseComponent)
        self.assertEqual(filegator.category, ComponentCategory.DOCKER_APPS.value)

    def test_filegator_declarative_get_plan_with_config(self):
        fg = FileGatorComponent(config={
            "host": "0.0.0.0",
            "host_port": 8990,
            "container_port": 80,
            "restart_policy": "unless-stopped",
        })
        plan = fg.get_plan()
        self.assertIsInstance(plan, ProvisionPlan)
        self.assertEqual(len(plan.steps), 1)

        step = plan.steps[0]
        self.assertEqual(step.component_name, "FileGator")
        self.assertEqual(len(step.install_commands), 2)
        self.assertIn("command -v docker", step.install_commands[0])
        self.assertIn("filegator/filegator", step.install_commands[1])
        self.assertIn("-p 0.0.0.0:8990:80", step.install_commands[1])
        self.assertIn("--restart unless-stopped", step.install_commands[1])

        self.assertEqual(len(step.validation_commands), 2)
        self.assertIn("docker info", step.validation_commands[0])
        self.assertIn("docker inspect", step.validation_commands[1])


class TestComponentRegistry(unittest.TestCase):

    def test_resolve_registered_slugs(self):
        self.assertIsInstance(ComponentRegistry.get("curl"), CurlComponent)
        self.assertIsInstance(ComponentRegistry.get("git"), GitComponent)
        self.assertIsInstance(ComponentRegistry.get("tailscale"), TailscaleComponent)
        self.assertIsInstance(ComponentRegistry.get("filegator"), FileGatorComponent)

    def test_python_is_not_in_registry(self):
        with self.assertRaises(ValueError):
            ComponentRegistry.get("python")

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
        synced_1 = self.service.sync_default_catalog()
        self.assertEqual(len(synced_1), 4)

        slugs = [c.slug for c in self.service.list_components()]
        self.assertIn("curl", slugs)
        self.assertIn("git", slugs)
        self.assertIn("tailscale", slugs)
        self.assertIn("filegator", slugs)
        self.assertNotIn("python", slugs)

        synced_2 = self.service.sync_default_catalog()
        self.assertEqual(len(synced_2), 4)

    def test_list_by_category(self):
        self.service.sync_default_catalog()
        native_components = self.service.list_components(category="native")
        self.assertEqual(len(native_components), 3)

        docker_components = self.service.list_components(category="docker_apps")
        self.assertEqual(len(docker_components), 1)
        self.assertEqual(docker_components[0].slug, "filegator")

    def test_port_conflict_validation(self):
        self.service.sync_default_catalog()
        items = [
            {"slug": "filegator", "config": {"host": "0.0.0.0", "host_port": 8990}},
            {"slug": "filegator", "config": {"host": "0.0.0.0", "host_port": 8990}},
        ]
        with self.assertRaises(DomainValidationError):
            self.service.validate_and_resolve_slugs(items)


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
        response = self.client.get("/components?category=docker_apps")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["slug"], "filegator")

    def test_get_component_by_slug(self):
        response = self.client.get("/components/filegator")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["slug"], "filegator")
        self.assertEqual(data["category"], "docker_apps")


if __name__ == "__main__":
    unittest.main()
