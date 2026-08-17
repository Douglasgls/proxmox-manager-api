import unittest
from unittest.mock import MagicMock, patch

from app.components.git_component import GitComponent
from app.components.curl_component import CurlComponent
from app.components.tailscale_component import TailscaleComponent
from app.components.base_system_component import BaseSystemComponent
from app.components.redis_component import RedisComponent
from app.components.postgresql_component import PostgresqlComponent
from app.components.native_component import NativeComponent
from app.components.docker_application_component import DockerApplicationComponent
from app.models.component import Component
from app.models.container import Container
from app.models.container_component import ContainerComponentStatus
from app.services.container_component_service import ContainerComponentService


class ConcreteBaseSystemComponent(BaseSystemComponent):
    def get_plan(self):
        return None


class TestComponentVersionDetection(unittest.TestCase):

    def test_git_component_version_detection(self):
        component = GitComponent()
        mock_session = MagicMock()
        mock_res = MagicMock()
        mock_res.exit_code = 0
        mock_res.stdout = "git version 2.43.0"
        mock_session.exec.return_value = mock_res

        version = component.get_installed_version(mock_session)
        self.assertEqual(version, "2.43.0")
        mock_session.exec.assert_called_with("git --version", timeout=30, raise_on_error=False)

    def test_curl_component_version_detection(self):
        component = CurlComponent()
        mock_session = MagicMock()
        mock_res = MagicMock()
        mock_res.exit_code = 0
        mock_res.stdout = "curl 7.88.1 (x86_64-pc-linux-gnu) libcurl/7.88.1"
        mock_session.exec.return_value = mock_res

        version = component.get_installed_version(mock_session)
        self.assertEqual(version, "7.88.1")

    def test_tailscale_component_version_detection(self):
        component = TailscaleComponent()
        mock_session = MagicMock()
        mock_res = MagicMock()
        mock_res.exit_code = 0
        mock_res.stdout = "1.56.1\n  tailscale commit: abcdef"
        mock_session.exec.return_value = mock_res

        version = component.get_installed_version(mock_session)
        self.assertEqual(version, "1.56.1")

    def test_base_system_component_version_detection(self):
        component = ConcreteBaseSystemComponent()
        mock_session = MagicMock()
        mock_res = MagicMock()
        mock_res.exit_code = 0
        mock_res.stdout = (
            'NAME="Debian GNU/Linux"\n'
            'VERSION_ID="12"\n'
            'VERSION="12 (bookworm)"\n'
            'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\n'
        )
        mock_session.exec.return_value = mock_res

        version = component.get_installed_version(mock_session)
        self.assertEqual(version, "Debian GNU/Linux 12 (bookworm)")

    def test_redis_docker_app_version_detection_via_env(self):
        component = RedisComponent()
        mock_session = MagicMock()

        res_label = MagicMock(exit_code=0, stdout="<no value>\n")
        res_env = MagicMock(exit_code=0, stdout="PATH=/usr/local/sbin:/usr/local/bin\nREDIS_VERSION=7.2.4\n")
        mock_session.exec.side_effect = [res_label, res_env]

        version = component.get_installed_version(mock_session)
        self.assertEqual(version, "7.2.4")

    def test_postgres_docker_app_version_detection_via_image_tag(self):
        component = PostgresqlComponent()
        mock_session = MagicMock()

        res_label = MagicMock(exit_code=0, stdout="<no value>\n")
        res_env = MagicMock(exit_code=0, stdout="PATH=/usr/bin\n")
        res_image = MagicMock(exit_code=0, stdout="postgres:16-alpine\n")
        mock_session.exec.side_effect = [res_label, res_env, res_image]

        version = component.get_installed_version(mock_session)
        self.assertEqual(version, "16-alpine")

    def test_container_component_service_uses_real_version_and_fallback(self):
        mock_repo = MagicMock()
        mock_engine = MagicMock()
        service = ContainerComponentService(repository=mock_repo, provision_engine=mock_engine)

        mock_container = MagicMock(spec=Container)
        mock_container.id = "c1"
        mock_container.container_number = 101

        mock_comp_db = MagicMock(spec=Component)
        mock_comp_db.id = "comp1"
        mock_comp_db.slug = "git"
        mock_comp_db.name = "git"

        mock_record = MagicMock()
        mock_repo.get_by_container_and_component.return_value = mock_record
        mock_repo.update_status.return_value = mock_record

        mock_provision_res = MagicMock()
        mock_provision_res.success = True
        mock_engine.execute.return_value = mock_provision_res

        mock_session = MagicMock()
        mock_session_res = MagicMock()
        mock_session_res.exit_code = 0
        mock_session_res.stdout = "git version 2.43.0"
        mock_session.exec.return_value = mock_session_res

        records = service.provision_container_components(
            container=mock_container,
            components=[mock_comp_db],
            session=mock_session,
        )

        self.assertEqual(len(records), 1)
        mock_repo.update_status.assert_called_with(
            container_component=mock_record,
            status=ContainerComponentStatus.INSTALLED.value,
            installed_version="2.43.0",
            config=None,
        )


if __name__ == "__main__":
    unittest.main()
