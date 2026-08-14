from typing import Any
from app.components.docker_application_component import DockerApplicationComponent


class JellyfinComponent(DockerApplicationComponent):
    """Componente de aplicação Docker para o Jellyfin (Servidor de Mídia)."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config)

    @property
    def name(self) -> str:
        return "Jellyfin"

    @property
    def slug(self) -> str:
        return "jellyfin"

    @property
    def image(self) -> str:
        return "jellyfin/jellyfin:latest"

    @property
    def container_name(self) -> str:
        return "jellyfin-app"

    @property
    def default_container_port(self) -> int:
        return 8096

    @property
    def default_host_port(self) -> int:
        return 8096

    @property
    def extra_ports(self) -> list[str]:
        # Porta 7359/udp é utilizada para auto-descoberta na rede local (DLNA/Network discovery)
        return ["7359:7359/udp"]

    @property
    def is_web_app(self) -> bool:
        return True

    @property
    def protocol(self) -> str:
        return "http"

    @property
    def description(self) -> str:
        return "Servidor de mídia de código aberto para organizar e transmitir filmes, séries e músicas."

    @property
    def website_url(self) -> str | None:
        return "https://jellyfin.org"

    @property
    def documentation_url(self) -> str | None:
        return "https://jellyfin.org/docs/"

    @property
    def default_volumes(self) -> list[str]:
        return [
            "jellyfin-config:/config",
            "jellyfin-cache:/cache",
            "jellyfin-media:/media",
        ]

    @property
    def volumes_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "jellyfin-config",
                "mount_path": "/config",
                "description": "Configurações de usuários, plugins e banco de metadados do Jellyfin",
            },
            {
                "name": "jellyfin-cache",
                "mount_path": "/cache",
                "description": "Arquivos temporários de cache e transcodificação de vídeo",
            },
            {
                "name": "jellyfin-media",
                "mount_path": "/media",
                "description": "Biblioteca e pastas contendo os arquivos de mídia (filmes, séries, músicas)",
            },
        ]
