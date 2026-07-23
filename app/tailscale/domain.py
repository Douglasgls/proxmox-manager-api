from dataclasses import dataclass


@dataclass(frozen=True)
class TailscaleProvisionParams:
    """Objeto de domínio contendo os parâmetros necessários para execução do `tailscale up`."""

    login_server: str
    auth_key: str
    hostname: str
