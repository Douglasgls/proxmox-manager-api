class ProxmoxConnectionError(Exception):
    """Raised when communication with the Proxmox host fails."""


class ProxmoxAPIError(Exception):
    """Raised when the Proxmox API returns an unexpected error."""


class ShellExecutionError(Exception):
    """Raised when a local Proxmox command fails."""


class ContainerNotFoundError(Exception):
    """Raised when a container cannot be found on Proxmox."""


class ContainerOperationError(Exception):
    """Raised when Proxmox rejects or fails a container operation."""
