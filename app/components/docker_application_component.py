from abc import ABC, abstractmethod
from typing import Any
from app.components.base_components import BaseComponent
from app.models.component import ComponentCategory
from app.provision.plan import ProvisionPlan
from app.provision.step import ProvisionStep


class DockerApplicationComponent(BaseComponent, ABC):
    """Classe base para componentes executados como aplicação Docker no container LXC."""

    @property
    def category(self) -> str:
        return ComponentCategory.DOCKER_APPLICATION.value

    @property
    @abstractmethod
    def image(self) -> str:
        """Imagem Docker a ser executada."""

    @property
    @abstractmethod
    def container_name(self) -> str:
        """Nome do container Docker."""

    @property
    def ports(self) -> list[str]:
        """Mapeamento de portas host:container. Padrão vazio se nenhuma porta for exposta."""
        return []

    def get_plan(self) -> ProvisionPlan:
        port_flags = " ".join([f"-p {p}" for p in self.ports])
        if port_flags:
            port_flags = " " + port_flags

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
            f"docker run -d --name {self.container_name} --restart always{port_flags} {self.image}; "
            f"fi; "
            f"fi"
        )

        # 3. Validação do container da aplicação Docker (sem dependência de curl)
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
