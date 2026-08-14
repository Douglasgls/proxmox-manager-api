from typing import Any
from app.components.docker_application_component import DockerApplicationComponent


class MariadbComponent(DockerApplicationComponent):
    """Componente de aplicação Docker para o MariaDB (Banco de Dados Relacional)."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config)

    @property
    def name(self) -> str:
        return "MariaDB"

    @property
    def slug(self) -> str:
        return "mariadb"

    @property
    def image(self) -> str:
        return "mariadb:11"

    @property
    def container_name(self) -> str:
        return "mariadb-app"

    @property
    def default_container_port(self) -> int:
        return 3306

    @property
    def default_host_port(self) -> int:
        return 3306

    @property
    def is_web_app(self) -> bool:
        return False

    @property
    def protocol(self) -> str:
        return "tcp"

    @property
    def description(self) -> str:
        return "Banco de dados relacional rápido, escalável e de alto desempenho compatível com MySQL."

    @property
    def website_url(self) -> str | None:
        return "https://mariadb.org"

    @property
    def documentation_url(self) -> str | None:
        return "https://mariadb.org/documentation/"

    @property
    def env_vars_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "MARIADB_ROOT_PASSWORD",
                "description": "Senha do superusuário root do banco de dados MariaDB",
                "required": True,
                "type": "password",
            },
            {
                "name": "MARIADB_DATABASE",
                "description": "Nome do banco de dados inicial a ser criado",
                "required": False,
                "type": "text",
            },
            {
                "name": "MARIADB_USER",
                "description": "Nome do usuário padrão adicional",
                "required": False,
                "type": "text",
            },
            {
                "name": "MARIADB_PASSWORD",
                "description": "Senha do usuário padrão adicional",
                "required": False,
                "type": "password",
            },
        ]

    @property
    def default_volumes(self) -> list[str]:
        return ["mariadb-data:/var/lib/mysql"]

    @property
    def volumes_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "mariadb-data",
                "mount_path": "/var/lib/mysql",
                "description": "Diretório de armazenamento permanente das tabelas e arquivos do MariaDB",
            }
        ]
