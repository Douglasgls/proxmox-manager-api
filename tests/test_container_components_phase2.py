import unittest
from unittest.mock import MagicMock
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.models.base import Base
from app.models.container import Container
from app.models.component import Component, ComponentCategory
from app.models.container_component import ContainerComponent, ContainerComponentStatus
from app.repositories.container_repository import ContainerRepository
from app.repositories.component_repository import ComponentRepository
from app.repositories.container_component_repository import ContainerComponentRepository
from app.services.component_service import ComponentService
from app.services.container_component_service import ContainerComponentService
from app.services.container_creation_workflow import ContainerCreationWorkflow
from app.services.container_service import ContainerService
from app.services.job_service import JobService
from app.dto.request.create_container import CreateContainerDTO
from app.dto.response.container import ContainerResponseDTO
from app.core.exceptions import DomainValidationError
from app.provision.engine import ProvisionEngine
from app.provision.result import ProvisionResult
from app.provision.step import ProvisionStep
from app.integrations.proxmox.container_session import ContainerSession
from app.main import app
from app.security.dependencies import get_current_user
from app.core.dependencies import get_db, get_component_service
from app.models.user import User


class TestPhase2ContainerComponents(unittest.TestCase):

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

    def test_legacy_payload_without_components_field(self):
        data = {"name": "c-legacy", "password": "pass"}
        dto = CreateContainerDTO.model_validate(data)
        self.assertEqual(dto.components, [])

        resolved = self.comp_service.validate_and_resolve_slugs(dto.components)
        self.assertEqual(resolved, [])

    def test_slug_deduplication(self):
        slugs = ["git", "git", "GIT"]
        resolved = self.comp_service.validate_and_resolve_slugs(slugs)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].slug, "git")

    def test_invalid_slug_fails_before_creation(self):
        slugs = ["git", "invalid_slug"]
        with self.assertRaises(DomainValidationError):
            self.comp_service.validate_and_resolve_slugs(slugs)

    def test_provision_single_component_success(self):
        container = Container(
            container_number=101,
            name="c-single",
            password="pass",
            cpu=1,
            memory_mb=512,
            disk_gb=2,
            status="running",
        )
        container = self.container_repo.create(container)

        mock_session = MagicMock(spec=ContainerSession)
        mock_session.exec.return_value = MagicMock(exit_code=0, stdout="2.39.0", stderr="", success=True)

        components = self.comp_service.validate_and_resolve_slugs(["git"])
        records = self.container_comp_service.provision_container_components(
            container=container,
            components=components,
            session=mock_session,
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].status, ContainerComponentStatus.INSTALLED.value)
        self.assertEqual(records[0].installed_version, "1.0.0")
        self.assertIsNotNone(records[0].installed_at)

    def test_provision_docker_app_with_custom_config(self):
        container = Container(
            container_number=102,
            name="c-filegator",
            password="pass",
            cpu=1,
            memory_mb=512,
            disk_gb=2,
            status="running",
        )
        container = self.container_repo.create(container)

        mock_session = MagicMock(spec=ContainerSession)
        mock_session.exec.return_value = MagicMock(exit_code=0, stdout="OK", stderr="", success=True)

        req_items = [
            {
                "slug": "filegator",
                "config": {
                    "host": "0.0.0.0",
                    "host_port": 8990,
                    "container_port": 80,
                    "restart_policy": "unless-stopped",
                }
            }
        ]
        components = self.comp_service.validate_and_resolve_slugs(req_items)
        records = self.container_comp_service.provision_container_components(
            container=container,
            components=components,
            session=mock_session,
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].status, ContainerComponentStatus.INSTALLED.value)
        self.assertIsNotNone(records[0].config)
        self.assertEqual(records[0].config["host_port"], 8990)
        self.assertEqual(records[0].config["container_port"], 80)
        self.assertEqual(records[0].config["host"], "0.0.0.0")

    def test_partial_failure_preserves_exact_state(self):
        container = Container(
            container_number=103,
            name="c-partial-fail",
            password="pass",
            cpu=1,
            memory_mb=512,
            disk_gb=2,
            status="running",
        )
        container = self.container_repo.create(container)

        mock_session = MagicMock(spec=ContainerSession)
        def mock_exec(cmd, timeout=300):
            if "git" in cmd:
                return MagicMock(exit_code=1, stdout="", stderr="apt-get install git failed", success=False)
            return MagicMock(exit_code=0, stdout="OK", stderr="", success=True)

        mock_session.exec.side_effect = mock_exec

        components = self.comp_service.validate_and_resolve_slugs(["curl", "git", "filegator"])
        
        self.container_comp_service.create_pending_records(container.id, components)

        records = self.container_comp_service.provision_container_components(
            container=container,
            components=components,
            session=mock_session,
        )

        all_db_records = self.container_comp_repo.list_by_container(container.id)
        self.assertEqual(len(all_db_records), 3)

        status_map = {r.component.slug: r.status for r in all_db_records}
        self.assertEqual(status_map["curl"], ContainerComponentStatus.INSTALLED.value)
        self.assertEqual(status_map["git"], ContainerComponentStatus.FAILED.value)
        self.assertEqual(status_map["filegator"], ContainerComponentStatus.PENDING.value)

    def test_container_response_dto_serialization(self):
        container = Container(
            container_number=104,
            name="c-dto",
            password="pass",
            cpu=1,
            memory_mb=512,
            disk_gb=2,
            status="running",
        )
        container = self.container_repo.create(container)
        fg_comp = self.comp_repo.get_by_slug("filegator")

        cc = ContainerComponent(
            container_id=container.id,
            component_id=fg_comp.id,
            status=ContainerComponentStatus.INSTALLED.value,
            installed_version="latest",
            config={"host": "0.0.0.0", "host_port": 8990, "container_port": 80},
            installed_at=datetime.now(),
        )
        self.container_comp_repo.create(cc)

        reloaded = self.container_repo.get(container.id)
        dto = ContainerResponseDTO.model_validate(reloaded)

        self.assertEqual(len(dto.components), 1)
        self.assertEqual(dto.components[0].slug, "filegator")
        self.assertEqual(dto.components[0].status, "INSTALLED")
        self.assertEqual(dto.components[0].config["host_port"], 8990)


class TestPhase2API(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

        comp_service = ComponentService(ComponentRepository(self.db))
        comp_service.sync_default_catalog()

        mock_user = MagicMock(spec=User)
        mock_user.id = "user-123"
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: self.db

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_post_container_invalid_component_returns_400(self):
        payload = {
            "name": "c-invalid-comp",
            "password": "secretpassword",
            "components": ["git", "django_invalid_slug"]
        }
        response = self.client.post("/containers", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Componente(s) não disponível(is)", response.json()["detail"])

    def test_post_container_components_success(self):
        container = Container(
            container_number=105,
            name="c-post-comp",
            password="pass",
            cpu=1,
            memory_mb=512,
            disk_gb=2,
            status="running",
        )
        container = ContainerRepository(self.db).create(container)

        payload = {
            "components": [
                "git",
                {
                    "slug": "filegator",
                    "config": {
                        "host": "0.0.0.0",
                        "host_port": 8990,
                        "container_port": 80
                    }
                }
            ]
        }
        response = self.client.post(f"/containers/{container.id}/components", json=payload)
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertIn("job_id", data)


if __name__ == "__main__":
    unittest.main()
