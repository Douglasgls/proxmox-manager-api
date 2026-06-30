import os
from typing import Any

from dotenv import load_dotenv
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException

from app.integrations.proxmox.exceptions import (
    ContainerNotFoundError,
    ContainerOperationError,
    ProxmoxAPIError,
    ProxmoxConnectionError,
    ShellExecutionError,
)
from app.integrations.proxmox.models import (
    ContainerInfo,
    ContainerStatus,
    OperationResult,
)
from app.integrations.proxmox.shell_executor import ShellExecutor


class ProxmoxClient:

    def __init__(
        self,
        shell_executor: ShellExecutor | None = None,
    ):
        load_dotenv()

        self.host = os.getenv("PROXMOX_HOST")
        self.user = os.getenv("PROXMOX_USER")
        self.token_name = os.getenv("PROXMOX_TOKEN_NAME")
        self.token_value = os.getenv("PROXMOX_TOKEN_VALUE")
        self.node = os.getenv("PROXMOX_NODE")
        self.verify_ssl = False
        self.default_storage = os.getenv("PROXMOX_DEFAULT_STORAGE")
        self.default_template = os.getenv("PROXMOX_DEFAULT_TEMPLATE")
        self.shell_executor = shell_executor or ShellExecutor()
        self._client = None

    def connect(self):
        if self._client is not None:
            return self._client

        missing = [
            name for name, value in {
                "PROXMOX_HOST": self.host,
                "PROXMOX_USER": self.user,
                "PROXMOX_TOKEN_NAME": self.token_name,
                "PROXMOX_TOKEN_VALUE": self.token_value,
                "PROXMOX_NODE": self.node,
            }.items()
            if not value
        ]

        if missing:
            raise ProxmoxConnectionError(
                f"Missing Proxmox environment variables: {', '.join(missing)}"
            )

        try:
            self._client = ProxmoxAPI(
                self.host,
                user=self.user,
                token_name=self.token_name,
                token_value=self.token_value,
                verify_ssl=self.verify_ssl,
            )
            self._client.version.get()
        except Exception as exc:
            self._client = None
            raise ProxmoxConnectionError(
                "Could not connect to Proxmox API"
            ) from exc

        return self._client

    def list_containers(self) -> list[ContainerInfo]:
        try:
            containers = self._node_api().lxc.get()
            return [
                self._container_from_summary(container)
                for container in containers
            ]
        except ResourceException as exc:
            if self._can_fallback(exc):
                return self._list_containers_shell()
            raise self._api_error(exc) from exc

    def get_container(
        self,
        container_id: int,
    ) -> ContainerInfo:
        try:
            current = self._lxc_api(container_id).status.current.get()
            return self._container_from_status(
                container_id=container_id,
                data=current,
            )
        except ResourceException as exc:
            if self._is_not_found(exc):
                raise ContainerNotFoundError(
                    f"Container {container_id} not found"
                ) from exc
            if self._can_fallback(exc):
                return self._get_container_shell(container_id)
            raise self._api_error(exc) from exc

    def start_container(
        self,
        container_id: int,
    ) -> OperationResult:
        return self._run_container_operation(
            container_id=container_id,
            operation="start",
            api_call=lambda: self._lxc_api(container_id).status.start.post(),
            shell_call=lambda: self.shell_executor.pct(
                "start",
                container_id,
            ),
        )

    def stop_container(
        self,
        container_id: int,
    ) -> OperationResult:
        return self._run_container_operation(
            container_id=container_id,
            operation="stop",
            api_call=lambda: self._lxc_api(container_id).status.stop.post(),
            shell_call=lambda: self.shell_executor.pct(
                "stop",
                container_id,
            ),
        )

    def restart_container(
        self,
        container_id: int,
    ) -> OperationResult:
        return self._run_container_operation(
            container_id=container_id,
            operation="restart",
            api_call=lambda: self._lxc_api(container_id).status.reboot.post(),
            shell_call=lambda: self.shell_executor.pct(
                "reboot",
                container_id,
            ),
        )

    def create_container(
        self,
        name: str,
        cpu: int,
        memory_mb: int,
        disk_gb: int = 2,
        image_name: str | None = None,
        storage: str | None = None,
    ) -> ContainerInfo:
        container_id = self._next_container_id()
        template = image_name or self.default_template
        target_storage = storage or self.default_storage

        if not template:
            raise ProxmoxAPIError(
                "Missing container template. Set image_name or PROXMOX_DEFAULT_TEMPLATE."
            )

        if not target_storage:
            target_storage = self._first_storage_id()

        params = {
            "vmid": container_id,
            "hostname": name,
            "ostemplate": template,
            "cores": cpu,
            "memory": memory_mb,
            "rootfs": f"{target_storage}:{disk_gb}",
            "unprivileged": 1,
            "start": 0,
        }

        try:
            self._node_api().lxc.post(**params)
        except ResourceException as exc:
            if self._can_fallback(exc):
                self.shell_executor.pct(
                    "create",
                    container_id,
                    template,
                    "--hostname",
                    name,
                    "--cores",
                    cpu,
                    "--memory",
                    memory_mb,
                    "--rootfs",
                    f"{target_storage}:{disk_gb}",
                    "--unprivileged",
                    1,
                )
            else:
                raise self._api_error(exc) from exc
        except ShellExecutionError:
            raise
        except Exception as exc:
            raise ProxmoxConnectionError(
                "Could not create container using Proxmox API"
            ) from exc

        return ContainerInfo(
            container_id=container_id,
            name=name,
            status="stopped",
            cpu=cpu,
            memory_mb=memory_mb,
            disk_gb=disk_gb,
            image_name=template,
        )

    def delete_container(
        self,
        container_id: int,
    ) -> OperationResult:
        return self._run_container_operation(
            container_id=container_id,
            operation="delete",
            api_call=lambda: self._lxc_api(container_id).delete(),
            shell_call=lambda: self.shell_executor.pct(
                "destroy",
                container_id,
            ),
            read_status_after=False,
            deleted=True,
        )

    def get_container_status(
        self,
        container_id: int,
    ) -> ContainerStatus:
        try:
            current = self._lxc_api(container_id).status.current.get()
            return self._status_from_api(
                container_id=container_id,
                data=current,
            )
        except ResourceException as exc:
            if self._is_not_found(exc):
                raise ContainerNotFoundError(
                    f"Container {container_id} not found"
                ) from exc
            if self._can_fallback(exc):
                return self._get_container_status_shell(container_id)
            raise self._api_error(exc) from exc

    def list_nodes(self) -> list[dict[str, Any]]:
        try:
            return self.connect().nodes.get()
        except ResourceException as exc:
            raise self._api_error(exc) from exc
        except Exception as exc:
            raise ProxmoxConnectionError(
                "Could not list Proxmox nodes"
            ) from exc

    def list_storage(self) -> list[dict[str, Any]]:
        try:
            return self._node_api().storage.get()
        except ResourceException as exc:
            raise self._api_error(exc) from exc
        except Exception as exc:
            raise ProxmoxConnectionError(
                "Could not list Proxmox storage"
            ) from exc

    def get_version(self) -> dict[str, Any]:
        try:
            return self.connect().version.get()
        except ResourceException as exc:
            raise self._api_error(exc) from exc
        except Exception as exc:
            raise ProxmoxConnectionError(
                "Could not get Proxmox version"
            ) from exc

    def _run_container_operation(
        self,
        container_id: int,
        operation: str,
        api_call,
        shell_call,
        read_status_after: bool = True,
        deleted: bool = False,
    ) -> OperationResult:
        try:
            api_call()
            status = None
            ip_address = None

            if deleted:
                status = "deleted"
            elif read_status_after:
                current_status = self.get_container_status(container_id)
                status = current_status.status
                ip_address = current_status.ip_address

            return OperationResult(
                container_id=container_id,
                operation=operation,
                success=True,
                message=f"Container {operation} executed using Proxmox API.",
                status=status,
                ip_address=ip_address,
            )
        except ResourceException as exc:
            if self._is_not_found(exc):
                raise ContainerNotFoundError(
                    f"Container {container_id} not found"
                ) from exc

            if not self._can_fallback(exc):
                raise self._api_error(exc) from exc

            return self._run_container_operation_shell(
                container_id=container_id,
                operation=operation,
                shell_call=shell_call,
                read_status_after=read_status_after,
                deleted=deleted,
            )
        except ShellExecutionError:
            raise
        except Exception as exc:
            raise ContainerOperationError(
                f"Could not execute container operation: {operation}"
            ) from exc

    def _run_container_operation_shell(
        self,
        container_id: int,
        operation: str,
        shell_call,
        read_status_after: bool,
        deleted: bool,
    ) -> OperationResult:
        shell_call()
        status = None
        ip_address = None

        if deleted:
            status = "deleted"
        elif read_status_after:
            current_status = self._get_container_status_shell(container_id)
            status = current_status.status
            ip_address = current_status.ip_address

        return OperationResult(
            container_id=container_id,
            operation=operation,
            success=True,
            message=f"Container {operation} executed using local shell fallback.",
            status=status,
            ip_address=ip_address,
        )

    def _node_api(self):
        return self.connect().nodes(self.node)

    def _lxc_api(
        self,
        container_id: int,
    ):
        return self._node_api().lxc(container_id)

    def _next_container_id(self) -> int:
        try:
            return int(self.connect().cluster.nextid.get())
        except ResourceException as exc:
            raise self._api_error(exc) from exc

    def _first_storage_id(self) -> str:
        storages = self.list_storage()

        for storage in storages:
            storage_id = storage.get("storage")
            if storage_id:
                return storage_id

        raise ProxmoxAPIError(
            "No Proxmox storage found for container creation"
        )

    def _list_containers_shell(self) -> list[ContainerInfo]:
        result = self.shell_executor.pct("list")
        lines = result.stdout.splitlines()
        containers: list[ContainerInfo] = []

        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 3:
                continue

            container_id = int(parts[0])
            status = parts[1]
            name = parts[2]
            containers.append(
                ContainerInfo(
                    container_id=container_id,
                    name=name,
                    status=status,
                    cpu=0,
                    memory_mb=0,
                )
            )

        return containers

    def _get_container_shell(
        self,
        container_id: int,
    ) -> ContainerInfo:
        status = self._get_container_status_shell(container_id)
        config = self._get_container_config_shell(container_id)

        return ContainerInfo(
            container_id=container_id,
            name=config.get("hostname", f"container-{container_id}"),
            status=status.status,
            cpu=int(config.get("cores", 0)),
            memory_mb=int(config.get("memory", 0)),
            disk_gb=self._disk_gb_from_rootfs(config.get("rootfs")),
            ip_address=status.ip_address,
            image_name=config.get("ostemplate"),
        )

    def _get_container_status_shell(
        self,
        container_id: int,
    ) -> ContainerStatus:
        result = self.shell_executor.pct(
            "status",
            container_id,
        )
        status = result.stdout.split()[-1]

        return ContainerStatus(
            container_id=container_id,
            status=status,
        )

    def _get_container_config_shell(
        self,
        container_id: int,
    ) -> dict[str, str]:
        result = self.shell_executor.pct(
            "config",
            container_id,
        )
        config: dict[str, str] = {}

        for line in result.stdout.splitlines():
            key, separator, value = line.partition(":")
            if separator:
                config[key.strip()] = value.strip()

        return config

    def _container_from_summary(
        self,
        data: dict[str, Any],
    ) -> ContainerInfo:
        container_id = int(data["vmid"])

        return ContainerInfo(
            container_id=container_id,
            name=data.get("name") or f"container-{container_id}",
            status=data.get("status", "unknown"),
            cpu=int(data.get("cpus") or data.get("cores") or 0),
            memory_mb=self._bytes_to_mb(data.get("maxmem")),
            disk_gb=self._bytes_to_gb(data.get("maxdisk")),
        )

    def _container_from_status(
        self,
        container_id: int,
        data: dict[str, Any],
    ) -> ContainerInfo:
        return ContainerInfo(
            container_id=container_id,
            name=data.get("name") or f"container-{container_id}",
            status=data.get("status", "unknown"),
            cpu=int(data.get("cpus") or data.get("cores") or 0),
            memory_mb=self._bytes_to_mb(data.get("maxmem")),
            disk_gb=self._bytes_to_gb(data.get("maxdisk")),
            ip_address=self._extract_ip_address(data),
        )

    def _status_from_api(
        self,
        container_id: int,
        data: dict[str, Any],
    ) -> ContainerStatus:
        status = data.get("status", "unknown")

        return ContainerStatus(
            container_id=container_id,
            status=status,
            uptime_seconds=data.get("uptime"),
            cpu_usage_percent=self._cpu_percent(data.get("cpu")),
            memory_usage_mb=self._bytes_to_mb(data.get("mem")),
            ip_address=(
                self._extract_ip_address(data)
                or self._read_container_ip_shell(container_id, status)
            ),
        )

    def _extract_ip_address(
        self,
        data: dict[str, Any],
    ) -> str | None:
        network = data.get("netin") or data.get("ip")

        if isinstance(network, str):
            return network

        return None

    def _read_container_ip_shell(
        self,
        container_id: int,
        status: str,
    ) -> str | None:
        if status != "running":
            return None

        try:
            result = self.shell_executor.pct(
                "exec",
                container_id,
                "--",
                "hostname",
                "-I",
                timeout=5,
            )
        except ShellExecutionError:
            return None

        addresses = result.stdout.split()

        if not addresses:
            return None

        return addresses[0]

    def _disk_gb_from_rootfs(
        self,
        rootfs: str | None,
    ) -> int | None:
        if not rootfs:
            return None

        _, _, value = rootfs.partition("size=")
        if not value:
            return None

        size = value.split(",")[0].upper()
        if size.endswith("G"):
            return int(float(size[:-1]))
        if size.endswith("M"):
            return int(float(size[:-1]) / 1024)

        return None

    def _api_error(
        self,
        exc: ResourceException,
    ) -> ProxmoxAPIError:
        return ProxmoxAPIError(
            str(exc)
        )

    def _is_not_found(
        self,
        exc: ResourceException,
    ) -> bool:
        return getattr(exc, "status_code", None) == 404

    def _can_fallback(
        self,
        exc: ResourceException,
    ) -> bool:
        return getattr(exc, "status_code", None) in {
            400,
            404,
            501,
            595,
        }

    def _bytes_to_mb(
        self,
        value,
    ) -> int:
        if value is None:
            return 0

        return int(int(value) / 1024 / 1024)

    def _bytes_to_gb(
        self,
        value,
    ) -> int | None:
        if value is None:
            return None

        return int(int(value) / 1024 / 1024 / 1024)

    def _cpu_percent(
        self,
        value,
    ) -> float | None:
        if value is None:
            return None

        return round(float(value) * 100, 2)

    def _env_bool(
        self,
        name: str,
        default: bool,
    ) -> bool:
        value = os.getenv(name)

        if value is None:
            return default

        return value.lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
