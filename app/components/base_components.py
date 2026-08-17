from abc import ABC, abstractmethod
from typing import Any
from app.provision.plan import ProvisionPlan
from app.provision.step import ProvisionStep


class BaseComponent(ABC):
    """Contrato base declarativo para componentes do sistema.
    
    Componentes produzem seu ProvisionPlan declarativo descrevendo comandos
    de instalação e validação. A execução física é conduzida exclusivamente pela ProvisionEngine.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @abstractmethod
    def get_plan(self) -> ProvisionPlan:
        """Constrói e retorna o ProvisionPlan declarativo para este componente."""

    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        """Retorna dados descritivos do componente."""

    @property
    def name(self) -> str:
        return self.metadata()["name"]

    def get_installed_version(self, session: Any) -> str | None:
        """Tenta consultar a versão real instalada no container através da sessão.

        Retorna None se a inspeção dinâmica não for suportada ou falhar.
        """
        return None

    def validate_config(self) -> None:
        """Valida a configuração informada para este componente."""
        pass

    def install(self, session: Any) -> str:
        """Executa os comandos de instalação do plano declarativo para compatibilidade direta."""
        plan = self.get_plan()
        count = 0
        for step in getattr(plan, "steps", []):
            for cmd in getattr(step, "install_commands", []):
                res = session.exec(cmd, timeout=300)
                if res and res.exit_code != 0:
                    raise Exception(
                        f"Erro executando comando de instalação '{cmd}':\n"
                        f"stdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
                    )
                count += 1
        return f"{count} comandos de instalação executados com sucesso."

    def validate(self, session: Any) -> str:
        """Executa os comandos de validação do plano declarativo para compatibilidade direta."""
        plan = self.get_plan()
        count = 0
        for step in getattr(plan, "steps", []):
            for cmd in getattr(step, "validation_commands", []):
                res = session.exec(cmd, timeout=60)
                if res and res.exit_code != 0:
                    raise Exception(
                        f"Validação falhou para o comando '{cmd}':\n"
                        f"stdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
                    )
                count += 1
        return f"{count} comandos de validação executados com sucesso."


