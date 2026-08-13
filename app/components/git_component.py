from typing import Any
from app.components.native_component import NativeComponent
from app.provision.plan import ProvisionPlan
from app.provision.step import ProvisionStep


class GitComponent(NativeComponent):

    def get_plan(self) -> ProvisionPlan:
        step = ProvisionStep(
            component_name=self.name,
            install_commands=[
                "apt-get update",
                "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git",
            ],
            validation_commands=[
                "git --version"
            ],
        )
        return ProvisionPlan(
            name="Git Provision Plan",
            description="Plano de instalação do Git",
            steps=[step],
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "name": "git",
            "description": "Instala o Git no sistema.",
            "version": "1.0.0",
        }