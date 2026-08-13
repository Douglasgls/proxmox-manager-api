from typing import Any
from app.components.docker_application_component import DockerApplicationComponent


class FileGatorComponent(DockerApplicationComponent):
    """Componente de aplicação Docker para o FileGator."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config)

    @property
    def name(self) -> str:
        return "FileGator"

    @property
    def slug(self) -> str:
        return "filegator"

    @property
    def image(self) -> str:
        return "filegator/filegator"

    @property
    def container_name(self) -> str:
        return "filegator-app"

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

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "slug": self.slug,
            "category": self.category,
            "description": "Navegador e gerenciador de arquivos web executado via container Docker.",
            "version": "latest",
            "image": self.image,
            "container_name": self.container_name,
            "default_config": {
                "host": self.default_host,
                "host_port": self.default_host_port,
                "container_port": self.default_container_port,
                "restart_policy": self.default_restart_policy,
            },
        }
