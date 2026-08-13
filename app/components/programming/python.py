from typing import Any
from app.components.native_component import NativeComponent
from app.provision.plan import ProvisionPlan
from app.provision.step import ProvisionStep


class PythonComponent(NativeComponent):
    """Componente para instalação declarativa do ambiente Python (categoria native)."""

    def get_plan(self) -> ProvisionPlan:
        step = ProvisionStep(
            component_name=self.name,
            install_commands=[
                "apt-get update",
                "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 python3-pip python3-venv",
            ],
            validation_commands=[
                "python3 --version",
            ],
        )
        return ProvisionPlan(
            name="Python Provision Plan",
            description="Plano de instalação do ambiente Python 3 e ferramentas base",
            steps=[step],
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "name": "python",
            "display_name": "Python",
            "category": self.category,
            "description": "Ambiente de Desenvolvimento e Execução Python 3 (com Pip e Venv).",
            "version": "3.10+",
        }
