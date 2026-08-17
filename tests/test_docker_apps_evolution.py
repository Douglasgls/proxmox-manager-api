import unittest
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.container import Container
from app.models.component import Component, ComponentCategory
from app.models.container_component import ContainerComponent, ContainerComponentStatus
from app.repositories.container_repository import ContainerRepository
from app.repositories.component_repository import ComponentRepository
from app.repositories.container_component_repository import ContainerComponentRepository
from app.services.component_service import ComponentService
from app.services.container_component_service import ContainerComponentService
from app.components.filegator_component import FileGatorComponent
from app.components.git_component import GitComponent
from app.core.exceptions import DomainValidationError
from app.dto.response.container import ContainerResponseDTO
from app.provision.engine import ProvisionEngine


class TestDockerAppsEvolution(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

        self.comp_repo = ComponentRepository(self.db)
        self.comp_service = ComponentService(self.comp_repo)
        self.comp_service.sync_default_catalog()

        self.container_comp_repo = ContainerComponentRepository(self.db)
        self.container_comp_service = ContainerComponentService(
            repository=self.container_comp_repo,
            provision_engine=ProvisionEngine(),
        )
        self.container_repo = ContainerRepository(self.db)

    def tearDown(self):
        self.db.close()

    # --- 1. Testes de Componentes Nativos ---

    def test_install_native_component_success(self):
        resolved = self.comp_service.validate_and_resolve_slugs(["git"])
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].slug, "git")
        self.assertEqual(resolved[0].category, ComponentCategory.NATIVE.value)

    def test_prevent_duplicate_native_component_installation(self):
        container = Container(
            container_number=101,
            name="c-native-test",
            password="pass",
            status="running",
        )
        container = self.container_repo.create(container)

        comp = self.comp_repo.get_by_slug("git")
        self.container_comp_repo.create_pending_record(container_id=container.id, component_id=comp.id)
        record = self.container_comp_repo.get_by_container_and_component(container.id, comp.id)
        self.container_comp_repo.update_status(record, status=ContainerComponentStatus.INSTALLED.value)

        existing = self.container_comp_repo.list_by_container(container.id)
        with self.assertRaises(DomainValidationError) as ctx:
            self.comp_service.validate_and_resolve_slugs(["git"], existing_container_components=existing)
        self.assertIn("já está instalado", str(ctx.exception))

    def test_deduplicate_native_component_in_same_batch(self):
        resolved = self.comp_service.validate_and_resolve_slugs(["git", "git", "GIT"])
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].slug, "git")

    # --- 2. Testes de Docker Apps & Múltiplas Instâncias ---

    def test_install_filegator_with_custom_port_and_name(self):
        item = {
            "slug": "filegator",
            "config": {
                "container_name": "meu-filegator",
                "host": "0.0.0.0",
                "host_port": 8990,
                "container_port": 80,
                "restart_policy": "unless-stopped",
            },
        }
        resolved = self.comp_service.validate_and_resolve_slugs([item])
        self.assertEqual(len(resolved), 1)

        comp_impl = self.comp_service.resolve_component_implementation("filegator", config=resolved[0]._request_config)
        plan = comp_impl.get_plan()
        plan_cmd = plan.steps[0].install_commands[1]
        self.assertIn("-p 0.0.0.0:8990:80", plan_cmd)
        self.assertIn("--name meu-filegator", plan_cmd)

    def test_allow_multiple_instances_of_filegator(self):
        items = [
            {
                "slug": "filegator",
                "config": {
                    "container_name": "filegator-1",
                    "host_port": 8080,
                },
            },
            {
                "slug": "filegator",
                "config": {
                    "container_name": "filegator-2",
                    "host_port": 8081,
                },
            },
        ]
        resolved = self.comp_service.validate_and_resolve_slugs(items)
        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[0]._request_config["container_name"], "filegator-1")
        self.assertEqual(resolved[1]._request_config["container_name"], "filegator-2")

    def test_prevent_container_name_conflict(self):
        container = Container(container_number=102, name="c-docker-test", password="pass", status="running")
        container = self.container_repo.create(container)

        comp = self.comp_repo.get_by_slug("filegator")
        rec = self.container_comp_repo.create_pending_record(
            container_id=container.id,
            component_id=comp.id,
            config={"container_name": "filegator-app", "host_port": 8080},
        )
        self.container_comp_repo.update_status(rec, status=ContainerComponentStatus.INSTALLED.value, config=rec.config)

        existing = self.container_comp_repo.list_by_container(container.id)
        item = {
            "slug": "filegator",
            "config": {"container_name": "filegator-app", "host_port": 8081},
        }
        with self.assertRaises(DomainValidationError) as ctx:
            self.comp_service.validate_and_resolve_slugs([item], existing_container_components=existing)
        self.assertIn("Conflito de nome", str(ctx.exception))

    def test_prevent_host_port_conflict(self):
        container = Container(container_number=103, name="c-port-test", password="pass", status="running")
        container = self.container_repo.create(container)

        comp = self.comp_repo.get_by_slug("filegator")
        rec = self.container_comp_repo.create_pending_record(
            container_id=container.id,
            component_id=comp.id,
            config={"container_name": "filegator-1", "host_port": 8080},
        )
        self.container_comp_repo.update_status(rec, status=ContainerComponentStatus.INSTALLED.value, config=rec.config)

        existing = self.container_comp_repo.list_by_container(container.id)
        item = {
            "slug": "filegator",
            "config": {"container_name": "filegator-2", "host_port": 8080},
        }
        with self.assertRaises(DomainValidationError) as ctx:
            self.comp_service.validate_and_resolve_slugs([item], existing_container_components=existing)
        self.assertIn("Conflito de porta", str(ctx.exception))

    def test_validate_invalid_host_port_range(self):
        item = {
            "slug": "filegator",
            "config": {"host_port": 70000},
        }
        with self.assertRaises(DomainValidationError) as ctx:
            self.comp_service.validate_and_resolve_slugs([item])
        self.assertIn("1 e 65535", str(ctx.exception))

    def test_validate_invalid_container_port_range(self):
        item = {
            "slug": "filegator",
            "config": {"container_port": 0},
        }
        with self.assertRaises(DomainValidationError) as ctx:
            self.comp_service.validate_and_resolve_slugs([item])
        self.assertIn("1 e 65535", str(ctx.exception))

    def test_validate_invalid_restart_policy(self):
        item = {
            "slug": "filegator",
            "config": {"restart_policy": "invalid-policy"},
        }
        with self.assertRaises(DomainValidationError) as ctx:
            self.comp_service.validate_and_resolve_slugs([item])
        self.assertIn("restart", str(ctx.exception))

    # --- 3. Testes do FileGator e Credenciais ---

    def test_filegator_custom_credentials_and_effective_config(self):
        fg = FileGatorComponent(config={
            "username": "myadmin",
            "password": "supersecretpassword123",
            "host_port": 8088,
        })
        fg.validate_config()
        effective = fg.get_effective_config()
        self.assertEqual(effective["username"], "myadmin")
        self.assertEqual(effective["password"], "supersecretpassword123")
        self.assertEqual(effective["host_port"], 8088)

        plan = fg.get_plan()
        run_cmd = plan.steps[0].install_commands[1]
        self.assertIn("FILEGATOR_USERNAME=\"myadmin\"", run_cmd)
        self.assertIn("FILEGATOR_PASSWORD=\"supersecretpassword123\"", run_cmd)

    def test_container_dto_masks_sensitive_passwords(self):
        item_dict = {
            "slug": "filegator",
            "name": "FileGator",
            "category": "docker_apps",
            "status": "INSTALLED",
            "installed_version": "latest",
            "config": {
                "host_port": 8080,
                "username": "admin",
                "password": "plain-text-password-123",
            },
            "error": None,
            "installed_at": None,
        }
        raw_container = {
            "id": "uuid-c1",
            "container_number": 101,
            "name": "c1",
            "status": "running",
            "cpu": 1,
            "memory_mb": 512,
            "disk_gb": 2,
            "components": [item_dict],
        }

        dto = ContainerResponseDTO.model_validate(raw_container)
        comp_dto = dto.components[0]
        self.assertEqual(comp_dto.config["username"], "admin")
        self.assertEqual(comp_dto.config["password"], "********")


if __name__ == "__main__":
    unittest.main()
