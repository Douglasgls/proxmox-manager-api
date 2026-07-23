import json
import logging
import shlex
from typing import Any

from app.integrations.proxmox.container_session import ContainerSession
from app.integrations.proxmox.models import CommandResult
from app.tailscale.domain import TailscaleProvisionParams

logger = logging.getLogger(__name__)



def mask_auth_key(auth_key: str) -> str:
    """Retorna a auth_key mascarada para exibição segura em logs."""
    if not auth_key:
        return ""
    if len(auth_key) <= 12:
        return auth_key[:4] + "************"
    return auth_key[:12] + "************"


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
        return result.success == True

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

    def exec_tailscale_up(self, params: TailscaleProvisionParams) -> CommandResult:
        """Executa `tailscale up` com login_server, auth_key e hostname mascarando a auth_key nos logs."""
        masked_key = mask_auth_key(params.auth_key)
        logger.info(
            "Executando tailscale up (login_server=%s, hostname=%s, auth_key=%s)",
            params.login_server,
            params.hostname,
            masked_key,
        )
        print(f"\n[TAILSCALE UP INÍCIO] Executando comando 'tailscale up' no container...")
        print(f"  -> Login Server: {params.login_server}")
        print(f"  -> Hostname:     {params.hostname}")
        print(f"  -> Auth Key:     {masked_key}\n")

        args = [
            "tailscale",
            "up",
            f"--login-server={params.login_server}",
            f"--authkey={params.auth_key}",
            f"--hostname={params.hostname}",
            "--accept-routes",
        ]

        result = self._exec(args, timeout=45)
        if result.exit_code != 0:
            safe_stderr = (result.stderr or "").replace(params.auth_key, masked_key)
            safe_stdout = (result.stdout or "").replace(params.auth_key, masked_key)
            print(f"\n[TAILSCALE UP ERRO] 'tailscale up' falhou com exit_code={result.exit_code}!\nstderr: {safe_stderr}\n")
            safe_result = CommandResult(
                success=result.success,
                command=result.command,
                stdout=safe_stdout,
                stderr=safe_stderr,
                exit_code=result.exit_code,
                duration=result.duration,
                executed_at=result.executed_at,
            )
            raise TailscaleCommandError(
                ["tailscale", "up", f"--login-server={params.login_server}", f"--authkey={masked_key}", f"--hostname={params.hostname}"],
                safe_result,
            )


        print(f"\n[TAILSCALE UP SUCESSO] 'tailscale up' concluído com sucesso!\n")
        return result


    def reset(self) -> CommandResult:
        """Reseta configurações ou remove auth do tailscale."""
        result = self._exec(["tailscale", "logout"])
        return result

