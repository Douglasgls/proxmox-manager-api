from abc import ABC, abstractmethod
from typing import Any
from app.components.base_components import BaseComponent
from app.models.component import ComponentCategory
from app.provision.plan import ProvisionPlan
from app.provision.step import ProvisionStep


class DockerApplicationComponent(BaseComponent, ABC):
    """Classe base para componentes executados como aplicação Docker no container LXC."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @property
    def category(self) -> str:
        return ComponentCategory.DOCKER_APPS.value

    @property
    @abstractmethod
    def image(self) -> str:
        """Imagem Docker a ser executada."""

    @property
    @abstractmethod
    def container_name(self) -> str:
        """Nome do container Docker."""

    @property
    def default_container_port(self) -> int:
        return 80

    @property
    def default_host_port(self) -> int:
        return 80

    @property
    def default_host(self) -> str:
        return "0.0.0.0"

    @property
    def default_restart_policy(self) -> str:
        return "unless-stopped"

    @property
    def container_port(self) -> int:
        val = self.config.get("container_port", self.default_container_port)
        return int(val)

    @property
    def host_port(self) -> int:
        val = self.config.get("host_port", self.default_host_port)
        return int(val)

    @property
    def host(self) -> str:
        return str(self.config.get("host", self.default_host))

    @property
    def restart_policy(self) -> str:
        return str(self.config.get("restart_policy", self.default_restart_policy))

    def get_effective_config(self) -> dict[str, Any]:
        """Retorna a configuração efetivamente utilizada nesta instância."""
        return {
            "host": self.host,
            "host_port": self.host_port,
            "container_port": self.container_port,
            "restart_policy": self.restart_policy,
        }

    def get_plan(self) -> ProvisionPlan:
        port_mapping = f"{self.host}:{self.host_port}:{self.container_port}"

        # 1. Garantir que o runtime Docker está instalado no LXC (idempotente)
        docker_install_cmd = (
            "if ! command -v docker >/dev/null 2>&1; then "
            "export DEBIAN_FRONTEND=noninteractive && "
            "apt-get update && "
            "apt-get install -y --no-install-recommends ca-certificates curl gnupg && "
            "install -m 0755 -d /etc/apt/keyrings && "
            "curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc && "
            "chmod a+r /etc/apt/keyrings/docker.asc && "
            "echo \"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable\" | tee /etc/apt/sources.list.d/docker.list > /dev/null && "
            "apt-get update && "
            "apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io && "
            "systemctl enable --now docker; "
            "fi"
        )

        docker_validate_cmd = "docker info >/dev/null 2>&1 || docker version"

        # 2. Execução idempotente do container da aplicação Docker
        app_run_cmd = (
            f"if ! docker ps -q --filter \"name={self.container_name}\" --filter \"status=running\" | grep -q .; then "
            f"if docker ps -aq --filter \"name={self.container_name}\" | grep -q .; then "
            f"docker start {self.container_name}; "
            f"else "
            f"docker run -d --name {self.container_name} --restart {self.restart_policy} -p {port_mapping} {self.image}; "
            f"fi; "
            f"fi"
        )

        # 3. Validação do container da aplicação Docker
        app_validate_cmd = (
            f"docker ps --filter \"name={self.container_name}\" --filter \"status=running\" | grep -q {self.container_name} && "
            f"[ \"$(docker inspect -f '{{{{.State.Running}}}}' {self.container_name} 2>/dev/null)\" = \"true\" ]"
        )

        step = ProvisionStep(
            component_name=self.name,
            install_commands=[
                docker_install_cmd,
                app_run_cmd,
            ],
            validation_commands=[
                docker_validate_cmd,
                app_validate_cmd,
            ],
        )

        return ProvisionPlan(
            name=f"{self.name.capitalize()} Docker Application Provision Plan",
            description=f"Plano de provisionamento para a aplicação Docker {self.name}",
            steps=[step],
        )
