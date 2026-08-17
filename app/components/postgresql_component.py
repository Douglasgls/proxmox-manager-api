from typing import Any
from app.components.docker_application_component import DockerApplicationComponent


class PostgresqlComponent(DockerApplicationComponent):
    """Componente de aplicação Docker para o PostgreSQL (Banco de Dados Relacional)."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config)

    @property
    def name(self) -> str:
        return "PostgreSQL"

    @property
    def slug(self) -> str:
        return "postgresql"

    @property
    def image(self) -> str:
        return "postgres:16-alpine"

    @property
    def default_container_name(self) -> str:
        return "postgres-app"

    @property
    def default_container_port(self) -> int:
        return 5432

    @property
    def default_host_port(self) -> int:
        return 5432

    @property
    def is_web_app(self) -> bool:
        return False

    @property
    def protocol(self) -> str:
        return "tcp"

    @property
    def description(self) -> str:
        return "Sistema gerenciador de banco de dados relacional de alto desempenho e código aberto."

    @property
    def website_url(self) -> str | None:
        return "https://www.postgresql.org"

    @property
    def documentation_url(self) -> str | None:
        return "https://www.postgresql.org/docs/"

    @property
    def default_env_vars(self) -> dict[str, str]:
        return {
            "POSTGRES_USER": "postgres",
            "POSTGRES_DB": "postgres",
        }

    @property
    def env_vars_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "POSTGRES_PASSWORD",
                "description": "Senha de acesso do superusuário do banco de dados PostgreSQL",
                "required": True,
                "type": "password",
            },
            {
                "name": "POSTGRES_USER",
                "description": "Nome do usuário inicial do banco de dados",
                "required": False,
                "default": "postgres",
                "type": "text",
            },
            {
                "name": "POSTGRES_DB",
                "description": "Nome do banco de dados padrão a ser criado na inicialização",
                "required": False,
                "default": "postgres",
                "type": "text",
            },
        ]

    @property
    def default_volumes(self) -> list[str]:
        return ["postgres-data:/var/lib/postgresql/data"]

    @property
    def volumes_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "postgres-data",
                "mount_path": "/var/lib/postgresql/data",
                "description": "Diretório de persistência dos dados e arquivos de tabelas do PostgreSQL",
            }
        ]
