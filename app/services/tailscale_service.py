import json
import shlex
from dataclasses import dataclass, field
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


@dataclass(slots=True)
class TailscaleLoginOptions:
    """Opcoes usadas para autenticar o node no servidor de controle."""

    auth_key: str | None = None
    login_server: str | None = None
    hostname: str | None = None
    advertise_routes: list[str] = field(default_factory=list)
    accept_routes: bool | None = None
    accept_dns: bool | None = None
    advertise_exit_node: bool = False
    ssh: bool = False
    reset: bool = False


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

        if result.exit_code != 0:
            raise TailscaleCommandError(args, result)

        return result

    @staticmethod
    def _bool(value: bool) -> str:
        """Converte valores booleanos para o formato aceito pela CLI do Tailscale."""
        return "true" if value else "false"

    @staticmethod
    def _option(name: str, value: str) -> str:
        """Monta uma opcao CLI no formato --nome=valor."""
        return f"--{name}={value}"

    @classmethod
    def _bool_option(cls, name: str, value: bool) -> str:
        """Monta uma opcao CLI booleana no formato esperado pelo Tailscale."""
        return cls._option(name, cls._bool(value))

    @classmethod
    def _routes_option(cls, routes: list[str]) -> str:
        """Monta a opcao de rotas anunciadas."""
        return cls._option("advertise-routes", ",".join(routes))

    def install_service(self) -> CommandResult:
        """Habilita e inicia o servico tailscaled no sistema."""
        return self._exec(["systemctl", "enable", "--now", "tailscaled"])

    def start(self) -> CommandResult:
        """Inicia o daemon tailscaled."""
        return self._exec(["systemctl", "start", "tailscaled"])

    def stop(self) -> CommandResult:
        """Para o daemon tailscaled."""
        return self._exec(["systemctl", "stop", "tailscaled"])

    def restart(self) -> CommandResult:
        """Reinicia o daemon tailscaled."""
        return self._exec(["systemctl", "restart", "tailscaled"])

    def enable(self) -> CommandResult:
        """Habilita o daemon tailscaled para iniciar com o sistema."""
        return self._exec(["systemctl", "enable", "tailscaled"])

    def disable(self) -> CommandResult:
        """Desabilita a inicializacao automatica do daemon tailscaled."""
        return self._exec(["systemctl", "disable", "tailscaled"])

    def status(self) -> str:
        """Retorna o status textual da rede Tailscale."""
        return self._exec(["tailscale", "status"]).stdout.strip()

    def status_json(self) -> dict[str, Any]:
        """Retorna o status da rede Tailscale em JSON."""
        stdout = self._exec(["tailscale", "status", "--json"]).stdout
        return json.loads(stdout)

    def ip(self) -> str:
        """Retorna o endereco IP Tailscale atribuido ao node."""
        return self._exec(["tailscale", "ip"]).stdout.strip()

    def version(self) -> str:
        """Retorna a versao instalada do Tailscale."""
        return self._exec(["tailscale", "version"]).stdout.strip()

    def is_running(self) -> bool:
        """Informa se o daemon tailscaled esta ativo."""
        result = self.session.exec(
            shlex.join(["systemctl", "is-active", "--quiet", "tailscaled"]),
            timeout=self.timeout,
        )
        return result.exit_code == 0

    def is_logged(self) -> bool:
        """Informa se o node esta autenticado no Tailscale."""
        result = self.session.exec(
            shlex.join(["tailscale", "status", "--json"]),
            timeout=self.timeout,
        )
        if result.exit_code != 0:
            return False

        status = json.loads(result.stdout)
        return bool(status.get("Self", {}).get("Online"))

    def up(
        self,
        *,
        auth_key: str | None = None,
        login_server: str | None = None,
        hostname: str | None = None,
        advertise_routes: list[str] | None = None,
        accept_routes: bool | None = None,
        accept_dns: bool | None = None,
        advertise_exit_node: bool = False,
        ssh: bool = False,
        reset: bool = False,
    ) -> CommandResult:
        """Executa tailscale up com as opcoes informadas."""
        options = TailscaleLoginOptions(
            auth_key=auth_key,
            login_server=login_server,
            hostname=hostname,
            advertise_routes=advertise_routes or [],
            accept_routes=accept_routes,
            accept_dns=accept_dns,
            advertise_exit_node=advertise_exit_node,
            ssh=ssh,
            reset=reset,
        )
        return self.login_with_options(options)

    def login(
        self,
        *,
        auth_key: str | None = None,
        login_server: str | None = None,
        hostname: str | None = None,
        advertise_routes: list[str] | None = None,
        accept_routes: bool | None = None,
        accept_dns: bool | None = None,
        advertise_exit_node: bool = False,
        ssh: bool = False,
        reset: bool = False,
    ) -> CommandResult:
        """Autentica o node no servidor de controle Tailscale ou Headscale."""
        return self.up(
            auth_key=auth_key,
            login_server=login_server,
            hostname=hostname,
            advertise_routes=advertise_routes,
            accept_routes=accept_routes,
            accept_dns=accept_dns,
            advertise_exit_node=advertise_exit_node,
            ssh=ssh,
            reset=reset,
        )

    def login_with_options(self, options: TailscaleLoginOptions) -> CommandResult:
        """Autentica o node usando um objeto de opcoes reutilizavel."""
        command = ["tailscale", "up"]

        if options.auth_key:
            command.append(self._option("auth-key", options.auth_key))
        if options.login_server:
            command.append(self._option("login-server", options.login_server))
        if options.hostname:
            command.append(self._option("hostname", options.hostname))
        if options.advertise_routes:
            command.append(self._routes_option(options.advertise_routes))
        if options.accept_routes is not None:
            command.append(self._bool_option("accept-routes", options.accept_routes))
        if options.accept_dns is not None:
            command.append(self._bool_option("accept-dns", options.accept_dns))
        if options.advertise_exit_node:
            command.append("--advertise-exit-node")
        if options.ssh:
            command.append("--ssh")
        if options.reset:
            command.append("--reset")

        return self._exec(command)

    def down(self) -> CommandResult:
        """Desconecta temporariamente o node da rede Tailscale."""
        return self._exec(["tailscale", "down"])

    def logout(self) -> CommandResult:
        """Remove a autenticacao atual do node."""
        return self._exec(["tailscale", "logout"])

    def set_hostname(self, hostname: str) -> CommandResult:
        """Atualiza o hostname anunciado pelo node."""
        return self._exec(["tailscale", "set", self._option("hostname", hostname)])

    def set_login_server(self, url: str) -> CommandResult:
        """Configura o servidor de login a ser usado pelo node."""
        return self._exec(["tailscale", "up", self._option("login-server", url)])

    def advertise_routes(self, routes: list[str]) -> CommandResult:
        """Anuncia rotas de rede atraves deste node."""
        return self._exec(["tailscale", "set", self._routes_option(routes)])

    def remove_routes(self) -> CommandResult:
        """Remove as rotas anunciadas por este node."""
        return self._exec(["tailscale", "set", "--advertise-routes="])

    def accept_routes(self, enabled: bool = True) -> CommandResult:
        """Ativa ou desativa a aceitacao de rotas anunciadas por outros nodes."""
        return self._exec(
            ["tailscale", "set", self._bool_option("accept-routes", enabled)]
        )

    def accept_dns(self, enabled: bool = True) -> CommandResult:
        """Ativa ou desativa o DNS gerenciado pelo Tailscale."""
        return self._exec(
            ["tailscale", "set", self._bool_option("accept-dns", enabled)]
        )

    def serve_status(self) -> str:
        """Retorna o status dos servicos publicados com tailscale serve."""
        return self._exec(["tailscale", "serve", "status"]).stdout.strip()

    def ping(self, target: str) -> str:
        """Executa um ping Tailscale para outro node."""
        return self._exec(["tailscale", "ping", target]).stdout.strip()

    def netcheck(self) -> str:
        """Executa diagnosticos de conectividade da rede Tailscale."""
        return self._exec(["tailscale", "netcheck"]).stdout.strip()

    def preferences(self) -> dict[str, Any]:
        """Retorna as preferencias locais do Tailscale."""
        stdout = self._exec(["tailscale", "debug", "prefs"]).stdout
        return json.loads(stdout)

    def debug(self) -> str:
        """Retorna informacoes de debug do Tailscale."""
        return self._exec(["tailscale", "debug"]).stdout.strip()
