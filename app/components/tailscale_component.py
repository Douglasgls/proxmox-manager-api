from typing import Any

from app.components.base_components import BaseComponent
from app.integrations.proxmox.container_session import ContainerSession


class TailscaleComponent(BaseComponent):
    """Componente responsavel apenas por instalar o Tailscale."""

    @property
    def name(self) -> str:
        """Retorna o nome usado pelo registry de componentes."""
        return "tailscale"

    def install(self, session: ContainerSession) -> str:
        """Instala dependencias, repositorio oficial e pacote tailscale."""
        result = session.exec(
            "export DEBIAN_FRONTEND=noninteractive && "
            "apt-get update && "
            "apt-get install -y --no-install-recommends ca-certificates curl gnupg && "
            "install -d -m 0755 /usr/share/keyrings && "
            "curl -fsSL https://pkgs.tailscale.com/stable/debian/bookworm.noarmor.gpg "
            "-o /usr/share/keyrings/tailscale-archive-keyring.gpg && "
            "curl -fsSL https://pkgs.tailscale.com/stable/debian/bookworm.tailscale-keyring.list "
            "-o /etc/apt/sources.list.d/tailscale.list && "
            "apt-get update && "
            "apt-get install -y --no-install-recommends tailscale",
            timeout=300,
        )

        if result.exit_code != 0:
            raise Exception(
                f"Erro instalando tailscale:\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}"
            )

        return "Tailscale instalado."

    def validate(self, session: ContainerSession) -> str:
        """Valida a instalacao executando tailscale version."""
        result = session.exec(
            "tailscale version",
            timeout=180,
        )

        if result.exit_code != 0:
            raise Exception(
                f"Tailscale validation failed:\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}"
            )

        return "Tailscale validado."

    def metadata(self) -> dict[str, Any]:
        """Retorna metadados descritivos do componente."""
        return {
            "name": self.name,
            "description": "Instala o Tailscale no sistema.",
            "version": "1.0.0",
        }

    def rollback(self, session: ContainerSession) -> None:
        """Remove pacote, repositorio e keyring do Tailscale."""
        session.exec(
            "export DEBIAN_FRONTEND=noninteractive && "
            "apt-get remove -y tailscale && "
            "rm -f /etc/apt/sources.list.d/tailscale.list && "
            "rm -f /usr/share/keyrings/tailscale-archive-keyring.gpg && "
            "apt-get update",
            timeout=180,
        )

    def execute(self, session: ContainerSession) -> None:
        """Mantem compatibilidade com a interface dos componentes existentes."""
        pass
