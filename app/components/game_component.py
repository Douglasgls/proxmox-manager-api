from typing import Any
from app.components.docker_application_component import DockerApplicationComponent


class GameComponent(DockerApplicationComponent):
    """Componente Docker Application para o jogo de teste (sithum/game)."""

    @property
    def image(self) -> str:
        return "sithum/game"

    @property
    def container_name(self) -> str:
        return "game-app"

    @property
    def ports(self) -> list[str]:
        return ["80:80"]

    def metadata(self) -> dict[str, Any]:
        return {
            "name": "game",
            "description": "Aplicação Web Game executada via container Docker.",
            "version": "1.0.0",
        }
