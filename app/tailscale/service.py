import json
import shlex
from typing import Any

from app.integrations.proxmox.container_session import ContainerSession
from app.integrations.proxmox.models import CommandResult


class TailscaleCommandError(RuntimeError):
    """Erro gerado quando um comando relacionado ao Tailscale falha."""

    def __init__(self, command: list[str], result: CommandResult):
        self.command = command
        self.result = result
        super().__init__(
            f"Erro executando comando Tailscale: {shlex.join(command)}\n"
            f"stdout:\n{result.stdout}\n\n"
            f"stderr:\n{result.stderr}"
        )


class TailscaleService:
    """Servico de alto nivel para controlar o Tailscale dentro do container."""

    def __init__(self, session: ContainerSession, timeout: int = 180):
        self.session = session
        self.timeout = timeout

    def _exec(self, args: list[str], timeout: int | None = None) -> CommandResult:
        """Executa um comando a partir de uma lista de argumentos com escaping seguro."""
        result = self.session.exec(
            shlex.join(args),
            timeout=timeout or self.timeout,
        )
        # Não raise error em todos, pois comandos como is_installed podem falhar (exit 1)
        return result

    def is_installed(self) -> bool:
        """Verifica se o tailscale está instalado no sistema."""
        result = self._exec(["tailscale", "version"])
        return result.exit_code == 0

    def start_service(self) -> CommandResult:
        """Inicia e habilita o daemon tailscaled."""
        result = self._exec(["systemctl", "enable", "--now", "tailscaled"])
        if result.exit_code != 0:
            raise TailscaleCommandError(["systemctl", "enable", "--now", "tailscaled"], result)
        return result

    def stop_service(self) -> CommandResult:
        """Para o daemon tailscaled."""
        result = self._exec(["systemctl", "stop", "tailscaled"])
        if result.exit_code != 0:
            raise TailscaleCommandError(["systemctl", "stop", "tailscaled"], result)
        return result

    def is_service_running(self) -> bool:
        """Informa se o daemon tailscaled esta ativo."""
        result = self.session.exec(
            shlex.join(["systemctl", "is-active", "--quiet", "tailscaled"]),
            timeout=self.timeout,
            raise_on_error=False,
        )
        return result.exit_code == 0

    def get_version(self) -> str | None:
        """Retorna a versao instalada do Tailscale."""
        result = self._exec(["tailscale", "version"])
        if result.exit_code == 0:
            return result.stdout.strip().split('\n')[0]
        return None

    def get_machine_id(self) -> str | None:
        """Retorna o machine-id do container."""
        result = self._exec(["cat", "/etc/machine-id"])
        if result.exit_code == 0:
            return result.stdout.strip()
        return None

    def get_node_key(self) -> str | None:
        """Retorna a public node key (Tailscale) atual do container."""
        status = self.get_status_json()
        if status:
            return status.get("Self", {}).get("PublicKey")
        return None

    def get_ip(self) -> str | None:
        """Retorna o endereco IP Tailscale atribuido ao node."""
        result = self._exec(["tailscale", "ip"])
        if result.exit_code == 0:
            return result.stdout.strip()
        return None

    def get_status_json(self) -> dict[str, Any] | None:
        """Retorna o status da rede Tailscale em JSON."""
        result = self._exec(["tailscale", "status", "--json"])
        if result.exit_code == 0 and result.stdout:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                pass
        return None

    def reset(self) -> CommandResult:
        """Reseta configurações ou remove auth do tailscale."""
        result = self._exec(["tailscale", "logout"])
        return result
