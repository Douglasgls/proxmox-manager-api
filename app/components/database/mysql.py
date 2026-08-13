from typing import Any
from app.components.database.base import DatabaseComponent
from app.provision.plan import ProvisionPlan
from app.provision.step import ProvisionStep


class MySQLComponent(DatabaseComponent):
    """Componente para instalação declarativa do MySQL."""

    def get_plan(self) -> ProvisionPlan:
        step = ProvisionStep(
            component_name=self.name,
            install_commands=[
                "apt-get update",
                "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends default-mysql-server",
            ],
            validation_commands=[
                "mysql --version",
            ],
        )
        return ProvisionPlan(
            name="MySQL Provision Plan",
            description="Plano de instalação do MySQL Database Server",
            steps=[step],
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "name": "mysql",
            "display_name": "MySQL",
            "category": self.category,
            "description": "Sistema Gerenciador de Banco de Dados Relacional MySQL.",
            "version": "8.0+",
        }
