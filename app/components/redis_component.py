from typing import Any
from app.components.docker_application_component import DockerApplicationComponent


class RedisComponent(DockerApplicationComponent):
    """Componente de aplicação Docker para o Redis (Cache e Armazenamento em Memória)."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config)

    @property
    def name(self) -> str:
        return "Redis"

    @property
    def slug(self) -> str:
        return "redis"

    @property
    def image(self) -> str:
        return "redis:7-alpine"

    @property
    def container_name(self) -> str:
        return "redis-app"

    @property
    def default_container_port(self) -> int:
        return 6379

    @property
    def default_host_port(self) -> int:
        return 6379

    @property
    def is_web_app(self) -> bool:
        return False

    @property
    def protocol(self) -> str:
        return "tcp"

    @property
    def description(self) -> str:
        return "Armazenamento de estrutura de dados em memória, utilizado como banco de dados, cache e mensagens."

    @property
    def website_url(self) -> str | None:
        return "https://redis.io"

    @property
    def documentation_url(self) -> str | None:
        return "https://redis.io/documentation"

    @property
    def env_vars_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "REDIS_PASSWORD",
                "description": "Senha de autenticação de clientes no servidor Redis (opcional)",
                "required": False,
                "type": "password",
            }
        ]

    @property
    def default_volumes(self) -> list[str]:
        return ["redis-data:/data"]

    @property
    def volumes_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "redis-data",
                "mount_path": "/data",
                "description": "Persistência em disco dos snapshots (RDB/AOF) do Redis",
            }
        ]
