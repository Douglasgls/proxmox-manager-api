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
        return "filegator/filegator:latest"

    @property
    def container_name(self) -> str:
        return "filegator-app"

    @property
    def default_container_port(self) -> int:
        return 8080

    @property
    def default_host_port(self) -> int:
        return 8080

    @property
    def default_host(self) -> str:
        return "0.0.0.0"

    @property
    def default_restart_policy(self) -> str:
        return "unless-stopped"

    @property
    def description(self) -> str:
        return "Navegador e gerenciador de arquivos web executado via container Docker."

    @property
    def website_url(self) -> str | None:
        return "https://filegator.io"

    @property
    def documentation_url(self) -> str | None:
        return "https://filegator.io/docs"

    @property
    def default_volumes(self) -> list[str]:
        return ["filegator-storage:/var/www/filegator/repository"]

    @property
    def volumes_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "filegator-storage",
                "mount_path": "/var/www/filegator/repository",
                "description": "Repositório persistente de arquivos do FileGator",
            }
        ]
