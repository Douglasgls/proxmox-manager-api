from typing import Any
from app.components.native_component import NativeComponent
from app.provision.plan import ProvisionPlan
from app.provision.step import ProvisionStep


class CurlComponent(NativeComponent):

    def get_plan(self) -> ProvisionPlan:
        step = ProvisionStep(
            component_name=self.name,
            install_commands=[
                "apt-get -o Acquire::Check-Valid-Until=false update",
                "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends curl",
            ],
            validation_commands=[
                "curl --version",
            ],
        )
        return ProvisionPlan(
            name="Curl Provision Plan",
            description="Plano de instalação do Curl",
            steps=[step],
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "name": "curl",
            "description": "Instala o cURL no sistema.",
            "version": "1.0.0",
        }