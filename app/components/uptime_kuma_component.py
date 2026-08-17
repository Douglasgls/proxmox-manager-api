from typing import Any
from app.components.docker_application_component import DockerApplicationComponent


class UptimeKumaComponent(DockerApplicationComponent):
    """Componente de aplicação Docker para o Uptime Kuma (Monitoramento)."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config)

    @property
    def name(self) -> str:
        return "Uptime Kuma"

    @property
    def slug(self) -> str:
        return "uptime-kuma"

    @property
    def image(self) -> str:
        return "louislam/uptime-kuma:1"

    @property
    def default_container_name(self) -> str:
        return "uptime-kuma-app"

    @property
    def default_container_port(self) -> int:
        return 3001

    @property
    def default_host_port(self) -> int:
        return 3001

    @property
    def is_web_app(self) -> bool:
        return True

    @property
    def protocol(self) -> str:
        return "http"

    @property
    def description(self) -> str:
        return "Ferramenta autohospedada de monitoramento de serviços e sites com belo painel de status."

    @property
    def website_url(self) -> str | None:
        return "https://uptime.kuma.pet"

    @property
    def documentation_url(self) -> str | None:
        return "https://github.com/louislam/uptime-kuma"

    @property
    def default_volumes(self) -> list[str]:
        return ["uptime-kuma-data:/app/data"]

    @property
    def volumes_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "uptime-kuma-data",
                "mount_path": "/app/data",
                "description": "Persistência de banco de dados SQLite, monitores e status do Uptime Kuma",
            }
        ]
