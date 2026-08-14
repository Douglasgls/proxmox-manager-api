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
    @abstractmethod
    def default_container_port(self) -> int:
        """Porta interna padrão exposta pela aplicação no container Docker."""

    @property
    def default_host_port(self) -> int:
        return self.default_container_port

    @property
    def default_host(self) -> str:
        return "0.0.0.0"

    @property
    def default_restart_policy(self) -> str:
        return "unless-stopped"

    @property
    def container_port(self) -> int:
        user_val = self.config.get("container_port")
        if user_val is not None:
            try:
                port = int(user_val)
                if 1 <= port <= 65535:
                    return port
            except (ValueError, TypeError):
                pass

        try:
            default_port = self.default_container_port
            if default_port is not None:
                port = int(default_port)
                if 1 <= port <= 65535:
                    return port
        except (ValueError, TypeError, NotImplementedError):
            pass

        raise ValueError(
            f"Porta interna do container (container_port) não definida para a aplicação Docker '{getattr(self, 'name', 'desconhecida')}'."
        )

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

    @property
    def is_web_app(self) -> bool:
        """Indica se a aplicação possui interface Web (HTTP)."""
        return True

    @property
    def protocol(self) -> str:
        """Protocolo principal da aplicação ('http' ou 'tcp')."""
        return "http"

    @property
    def website_url(self) -> str | None:
        return None

    @property
    def documentation_url(self) -> str | None:
        return None

    @property
    def default_env_vars(self) -> dict[str, str]:
        return {}

    @property
    def default_volumes(self) -> list[str]:
        return []

    @property
    def extra_ports(self) -> list[str]:
        """Portas secundárias para mapeamento no container Docker (ex: '7359:7359/udp')."""
        return []

    @property
    def env_vars_schema(self) -> list[dict[str, Any]]:
        """Esquema de variáveis de ambiente para orientação e validação no front-end."""
        return []

    @property
    def volumes_schema(self) -> list[dict[str, Any]]:
        """Esquema de volumes de persistência da aplicação."""
        return []

    @property
    def env_vars(self) -> dict[str, str]:
        """Retorna o dicionário mesclado de variáveis de ambiente."""
        merged = dict(self.default_env_vars)
        user_env = self.config.get("env") or self.config.get("env_vars") or {}
        if isinstance(user_env, dict):
            for k, v in user_env.items():
                if v is not None:
                    merged[str(k)] = str(v)
        elif isinstance(user_env, list):
            for item in user_env:
                if "=" in str(item):
                    k, v = str(item).split("=", 1)
                    merged[k.strip()] = v.strip()
        return merged

    @property
    def volumes(self) -> list[str]:
        """Retorna a lista de volumes mapeados."""
        user_vols = self.config.get("volumes")
        if user_vols:
            if isinstance(user_vols, list):
                return [str(v) for v in user_vols]
            elif isinstance(user_vols, dict):
                return [f"{k}:{v}" for k, v in user_vols.items()]
        return list(self.default_volumes)

    def validate_config(self) -> None:
        """Valida se todas as variáveis obrigatórias do esquema foram fornecidas."""
        effective_envs = self.env_vars
        for schema in self.env_vars_schema:
            if schema.get("required"):
                name = schema.get("name")
                val = effective_envs.get(name)
                if not val or not str(val).strip():
                    raise ValueError(
                        f"A variável de ambiente obrigatória '{name}' não foi informada para a aplicação '{self.name}'."
                    )

    def get_effective_config(self) -> dict[str, Any]:
        """Retorna a configuração efetivamente utilizada nesta instância."""
        return {
            "host": self.host,
            "host_port": self.host_port,
            "container_port": self.container_port,
            "restart_policy": self.restart_policy,
            "env": self.env_vars,
            "volumes": self.volumes,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "slug": self.slug,
            "category": self.category,
            "description": getattr(self, "description", ""),
            "version": "latest",
            "image": self.image,
            "container_name": self.container_name,
            "is_web_app": self.is_web_app,
            "protocol": self.protocol,
            "website_url": self.website_url,
            "documentation_url": self.documentation_url,
            "default_config": {
                "host": self.default_host,
                "host_port": self.default_host_port,
                "container_port": self.default_container_port,
                "restart_policy": self.default_restart_policy,
                "env": self.default_env_vars,
                "volumes": self.default_volumes,
            },
            "env_vars_schema": self.env_vars_schema,
            "volumes_schema": self.volumes_schema,
        }

    def get_plan(self) -> ProvisionPlan:
        self.validate_config()

        port_mapping = f"{self.host}:{self.host_port}:{self.container_port}"
        extra_ports_str = ""
        if self.extra_ports:
            extra_ports_str = " " + " ".join(f"-p {p}" for p in self.extra_ports)

        env_args = ""
        if self.env_vars:
            env_args = " " + " ".join(f"-e {k}=\"{v}\"" for k, v in self.env_vars.items())

        vol_args = ""
        if self.volumes:
            vol_args = " " + " ".join(f"-v {v}" for v in self.volumes)

        # 1. Garantir que o runtime Docker está instalado no LXC (idempotente)
        docker_install_cmd = (
            "if ! command -v docker >/dev/null 2>&1; then "
            "export DEBIAN_FRONTEND=noninteractive && "
            "apt-get -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false update && "
            "apt-get install -y --no-install-recommends ca-certificates curl gnupg && "
            "install -m 0755 -d /etc/apt/keyrings && "
            "curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc && "
            "chmod a+r /etc/apt/keyrings/docker.asc && "
            "echo \"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable\" | tee /etc/apt/sources.list.d/docker.list > /dev/null && "
            "apt-get -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false update && "
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
            f"docker run -d --name {self.container_name} --restart {self.restart_policy} -p {port_mapping}{extra_ports_str}{env_args}{vol_args} {self.image}; "
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
