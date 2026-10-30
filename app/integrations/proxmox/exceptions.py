class ProxmoxConnectionError(Exception):
    """Raised when communication with the Proxmox host fails."""

    def __init__(self, message: str = "Falha na comunicação com o Proxmox VE"):
        super().__init__(message)
        self.message = message


class ProxmoxAPIError(Exception):
    """Raised when the Proxmox API returns an unexpected error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ProxmoxPermissionError(ProxmoxAPIError):
    """Raised when Proxmox rejects an action due to missing ACL permissions (403 Forbidden)."""

    def __init__(
        self,
        message: str,
        required_permission: str | None = None,
        path: str | None = None,
    ):
        super().__init__(message, status_code=403)
        self.required_permission = required_permission
        self.path = path


class ShellExecutionError(Exception):
    """Raised when a local Proxmox command fails."""

    def __init__(
        self,
        message: str,
        result=None,
    ):
        super().__init__(
            message
        )
        self.result = result


class ContainerNotFoundError(Exception):
    """Raised when a container cannot be found on Proxmox."""


class ContainerOperationError(Exception):
    """Raised when Proxmox rejects or fails a container operation."""
