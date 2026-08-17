import re
from abc import ABC
from typing import Any
from app.components.base_components import BaseComponent
from app.models.component import ComponentCategory


class NativeComponent(BaseComponent, ABC):
    """Classe base para componentes instalados diretamente no container LXC (categoria native)."""

    @property
    def category(self) -> str:
        return ComponentCategory.NATIVE.value

    @property
    def version_command(self) -> str | None:
        """Comando shell a ser executado no container para retornar a versão do componente."""
        return None

    @property
    def package_name(self) -> str | None:
        """Nome do pacote dpkg/apt instalado no sistema."""
        return None

    def get_installed_version(self, session: Any) -> str | None:
        """Consulta a versão real instalada do pacote nativo via sessão LXC."""
        cmd = self.version_command
        if not cmd and self.package_name:
            cmd = f"dpkg-query -W -f='${{Version}}' {self.package_name}"

        if not cmd:
            return None

        try:
            res = session.exec(cmd, timeout=30, raise_on_error=False)
            if res and res.exit_code == 0 and res.stdout:
                return self._extract_version_string(res.stdout)
        except Exception:
            pass

        return None

    @staticmethod
    def _extract_version_string(output: str) -> str | None:
        """Extrai o padrão numérico de versão a partir da saída de um comando."""
        text = output.strip()
        if not text:
            return None
        match = re.search(r"(\d+\.\d+(?:\.\d+)?(?:[~+.\-\w]+)?)", text)
        if match:
            return match.group(1)
        return text.splitlines()[0] if text else None

