from typing import Any
from app.components.native_component import NativeComponent
from app.provision.plan import ProvisionPlan
from app.provision.step import ProvisionStep


class TailscaleComponent(NativeComponent):
    """Componente responsavel por instalar o Tailscale (categoria native)."""

    def get_plan(self) -> ProvisionPlan:
        step = ProvisionStep(
            component_name=self.name,
            install_commands=[
                "export DEBIAN_FRONTEND=noninteractive && "
                "apt-get update && "
                "apt-get install -y --no-install-recommends ca-certificates curl gnupg && "
                "install -d -m 0755 /usr/share/keyrings && "
                "curl -fsSL https://pkgs.tailscale.com/stable/debian/bookworm.noarmor.gpg "
                "-o /usr/share/keyrings/tailscale-archive-keyring.gpg && "
                "curl -fsSL https://pkgs.tailscale.com/stable/debian/bookworm.tailscale-keyring.list "
                "-o /etc/apt/sources.list.d/tailscale.list && "
                "apt-get update && "
                "apt-get install -y --no-install-recommends tailscale"
            ],
            validation_commands=[
                "tailscale version"
            ],
        )
        return ProvisionPlan(
            name="Tailscale Provision Plan",
            description="Plano de instalação do Tailscale",
            steps=[step],
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": "Instala o Tailscale no sistema.",
            "version": "1.0.0",
        }
