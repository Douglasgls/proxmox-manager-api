import json
import logging
import os
from datetime import datetime
import time
from time import perf_counter
from time import sleep
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
    CommandResult,
    ContainerInfo,
    ContainerStatus,
    NetworkBridge,
    OperationResult,
    TemplateOperationResult,
)
from app.integrations.proxmox.network_configuration_formatter import (
    ProxmoxNetworkConfigurationFormatter,
)
from app.integrations.proxmox.shell_executor import ShellExecutor
from app.models.network_configuration import NetworkConfiguration
from app.models.os_template import OsTemplate


logger = logging.getLogger(__name__)


class ProxmoxClient:

    def __init__(
        self,
        shell_executor: ShellExecutor | None = None,
        network_formatter: ProxmoxNetworkConfigurationFormatter | None = None,
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
        self.network_formatter = (
            network_formatter
            or ProxmoxNetworkConfigurationFormatter()
        )
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
        network: NetworkConfiguration,
        disk_gb: int = 2,
        image_name: str | None = None,
        storage: str | None = None,
        password: str | None = None,
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
            "password": password,
            "ostemplate": template,
            "cores": cpu,
            "memory": memory_mb,
            "rootfs": f"{target_storage}:{disk_gb}",
            "net0": self._build_net0(network),
            "unprivileged": 1,
            "start": 0,
        }

        try:
            upid =  self._node_api().lxc.post(**params)
            print(f"Created container with id {container_id}: {upid}")

            # Espera a criação do container terminar
            while True:
                task = self._node_api().tasks(upid).status.get()

                if task["status"] == "stopped":
                    if task.get("exitstatus") != "OK":
                        raise RuntimeError(task.get("exitstatus"))
                    break

                time.sleep(1)
            
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
                    "--net0",
                    self._build_net0(network),
                    "--unprivileged",
                    1,
                    "--password",
                    password,
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
            ip_address=network.ip_address,
            image_name=template,
        )

    def update_container_network(
        self,
        container_id: int,
        network: NetworkConfiguration,
    ) -> OperationResult:
        net0 = self._build_net0(
            network
        )

        try:
            self._lxc_api(container_id).config.put(
                net0=net0
            )
            current_status = self.get_container_status(
                container_id
            )

            return OperationResult(
                container_id=container_id,
                operation="update_network",
                success=True,
                message="Container network updated using Proxmox API.",
                status=current_status.status,
                ip_address=current_status.ip_address,
            )
        except ResourceException as exc:
            if self._is_not_found(exc):
                raise ContainerNotFoundError(
                    f"Container {container_id} not found"
                ) from exc

            if not self._can_fallback(exc):
                raise self._api_error(exc) from exc

            return self._update_container_network_shell(
                container_id=container_id,
                net0=net0,
            )
        except ShellExecutionError:
            raise
        except Exception as exc:
            raise ContainerOperationError(
                "Could not update container network"
            ) from exc

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

    def list_networks(self) -> list[NetworkBridge]:
        try:
            networks = self._node_api().network.get(
                type="bridge"
            )
            return [
                self._network_bridge_from_data(network)
                for network in networks
                if self._is_bridge_network(network)
            ]
        except ResourceException as exc:
            if self._can_fallback(exc):
                return self._list_networks_shell()
            raise self._api_error(exc) from exc
        except ShellExecutionError:
            raise
        except Exception as exc:
            raise ProxmoxConnectionError(
                "Could not list Proxmox networks"
            ) from exc

    def list_available_templates(self) -> list[OsTemplate]:
        try:
            templates = self._node_api().aplinfo.get()
            return [
                self._available_template_from_data(template)
                for template in templates
            ]
        except ResourceException as exc:
            if self._can_fallback(exc):
                return self._list_available_templates_shell()
            raise self._api_error(exc) from exc
        except ShellExecutionError:
            raise
        except Exception as exc:
            raise ProxmoxConnectionError(
                "Could not list available Proxmox templates"
            ) from exc

    def list_installed_templates(self) -> list[OsTemplate]:
        templates: list[OsTemplate] = []

        for storage in self._template_storages():
            templates.extend(
                self._list_installed_templates_by_storage(
                    storage
                )
            )

        return templates

    def download_template(
        self,
        storage: str,
        template: str,
    ) -> TemplateOperationResult:
        try:
            task_id = self._node_api().aplinfo.post(
                storage=storage,
                template=template,
            )
            self._wait_for_task(
                task_id
            )

            return TemplateOperationResult(
                operation="download_template",
                success=True,
                message="Template downloaded using Proxmox API.",
                storage=storage,
                template=template,
                task_id=str(task_id),
            )
        except ResourceException as exc:
            if self._can_fallback(exc):
                return self._download_template_shell(
                    storage=storage,
                    template=template,
                )
            raise self._api_error(exc) from exc
        except ProxmoxAPIError:
            raise
        except ShellExecutionError:
            raise
        except Exception as exc:
            raise ProxmoxConnectionError(
                "Could not download Proxmox template"
            ) from exc

    def delete_template(
        self,
        template: str,
    ) -> TemplateOperationResult:
        storage = self._template_storage(
            template
        )

        try:
            self._node_api().storage(storage).content(template).delete()

            return TemplateOperationResult(
                operation="delete_template",
                success=True,
                message="Template deleted using Proxmox API.",
                storage=storage,
                template=template,
            )
        except ResourceException as exc:
            if self._can_fallback(exc):
                return self._delete_template_shell(
                    template
                )
            raise self._api_error(exc) from exc
        except ShellExecutionError:
            raise
        except Exception as exc:
            raise ProxmoxConnectionError(
                "Could not delete Proxmox template"
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

    def exec(
        self,
        container_id: int,
        command: str,
    ) -> CommandResult:
        """Executa um comando administrativo dentro de um container LXC."""
        return self._exec_container_command_shell(
            container_id=container_id,
            command=command,
        )

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

    def _exec_container_command_shell(
        self,
        container_id: int,
        command: str,
    ) -> CommandResult:
        executed_at = datetime.now()
        started_at = perf_counter()

        logger.info(
            "Executando comando via pct exec no container %s",
            container_id,
        )

        try:
            result = self.shell_executor.pct(
                "exec",
                container_id,
                "--",
                "sh",
                "-lc",
                command,
            )

            return self._command_result_from_shell(
                command=command,
                executed_at=executed_at,
                duration=perf_counter() - started_at,
                success=True,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
            )
        except ShellExecutionError as exc:
            shell_result = getattr(
                exc,
                "result",
                None,
            )

            logger.warning(
                "Comando falhou no container %s: %s",
                container_id,
                command,
            )

            return self._command_result_from_shell(
                command=command,
                executed_at=executed_at,
                duration=perf_counter() - started_at,
                success=False,
                stdout=(
                    shell_result.stdout
                    if shell_result
                    else ""
                ),
                stderr=(
                    shell_result.stderr
                    if shell_result
                    else str(exc)
                ),
                exit_code=(
                    shell_result.exit_code
                    if shell_result
                    else 1
                ),
            )

    def _command_result_from_shell(
        self,
        command: str,
        executed_at: datetime,
        duration: float,
        success: bool,
        stdout: str,
        stderr: str,
        exit_code: int,
    ) -> CommandResult:
        return CommandResult(
            success=success,
            command=command,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration=duration,
            executed_at=executed_at,
        )

    def _update_container_network_shell(
        self,
        container_id: int,
        net0: str,
    ) -> OperationResult:
        self.shell_executor.pct(
            "set",
            container_id,
            "--net0",
            net0,
        )

        current_status = self._get_container_status_shell(
            container_id
        )

        return OperationResult(
            container_id=container_id,
            operation="update_network",
            success=True,
            message="Container network updated using local shell fallback.",
            status=current_status.status,
            ip_address=current_status.ip_address,
        )

    def _build_net0(
        self,
        network: NetworkConfiguration,
    ) -> str:

        return self.network_formatter.build_net0(
            network
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

    def _template_storages(self) -> list[str]:
        return [
            storage["storage"]
            for storage in self.list_storage()
            if storage.get("storage")
            and self._storage_supports_templates(storage)
        ]

    def _storage_supports_templates(
        self,
        storage: dict[str, Any],
    ) -> bool:

        content = storage.get("content")

        if not content:
            return True

        return "vztmpl" in str(content).split(",")

    def _list_installed_templates_by_storage(
        self,
        storage: str,
    ) -> list[OsTemplate]:
        try:
            templates = self._node_api().storage(storage).content.get(
                content="vztmpl"
            )
            return [
                self._installed_template_from_data(
                    template,
                    storage,
                )
                for template in templates
                if template.get("content") in {
                    None,
                    "vztmpl",
                }
            ]
        except ResourceException as exc:
            if self._can_fallback(exc):
                return self._list_installed_templates_shell(
                    storage
                )
            raise self._api_error(exc) from exc

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

    def _list_available_templates_shell(self) -> list[OsTemplate]:
        result = self.shell_executor.pveam(
            "available"
        )
        templates: list[OsTemplate] = []

        for line in result.stdout.splitlines():
            filename = self._template_filename_from_line(
                line
            )

            if filename:
                templates.append(
                    self._template_from_filename(
                        filename=filename,
                        downloaded=False,
                        source="available",
                    )
                )

        return templates

    def _list_installed_templates_shell(
        self,
        storage: str,
    ) -> list[OsTemplate]:
        result = self.shell_executor.pveam(
            "list",
            storage,
        )
        templates: list[OsTemplate] = []

        for line in result.stdout.splitlines():
            volume_id = self._template_volume_id_from_line(
                line
            )

            if not volume_id:
                continue

            template_storage = self._template_storage(
                volume_id
            )
            filename = self._template_filename(
                volume_id
            )
            templates.append(
                self._template_from_filename(
                    filename=filename,
                    storage=template_storage,
                    downloaded=True,
                    source="installed",
                    size=self._template_size_from_line(line),
                )
            )

        return templates

    def _download_template_shell(
        self,
        storage: str,
        template: str,
    ) -> TemplateOperationResult:
        self.shell_executor.pveam(
            "download",
            storage,
            template,
            timeout=600,
        )

        return TemplateOperationResult(
            operation="download_template",
            success=True,
            message="Template downloaded using local shell fallback.",
            storage=storage,
            template=template,
        )

    def _delete_template_shell(
        self,
        template: str,
    ) -> TemplateOperationResult:
        self.shell_executor.pveam(
            "remove",
            template,
        )

        return TemplateOperationResult(
            operation="delete_template",
            success=True,
            message="Template deleted using local shell fallback.",
            storage=self._template_storage(template),
            template=template,
        )

    def _list_networks_shell(self) -> list[NetworkBridge]:
        result = self.shell_executor.pvesh(
            "get",
            f"/nodes/{self.node}/network",
            "--type",
            "bridge",
            "--output-format",
            "json",
        )
        networks = json.loads(
            result.stdout
        )

        return [
            self._network_bridge_from_data(network)
            for network in networks
            if self._is_bridge_network(network)
        ]

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

    def _available_template_from_data(
        self,
        data: dict[str, Any],
    ) -> OsTemplate:

        filename = (
            data.get("template")
            or data.get("package")
            or data.get("filename")
        )

        return self._template_from_filename(
            filename=filename,
            distribution=data.get("os"),
            version=data.get("version"),
            description=(
                data.get("headline")
                or data.get("description")
            ),
            downloaded=False,
            size=data.get("size"),
            source="available",
        )

    def _installed_template_from_data(
        self,
        data: dict[str, Any],
        storage: str,
    ) -> OsTemplate:

        volume_id = data.get("volid") or data.get("volume")
        filename = self._template_filename(
            volume_id
        )

        return self._template_from_filename(
            filename=filename,
            storage=storage,
            downloaded=True,
            size=data.get("size"),
            source="installed",
        )

    def _template_from_filename(
        self,
        filename: str,
        distribution: str | None = None,
        version: str | None = None,
        description: str | None = None,
        storage: str | None = None,
        downloaded: bool = False,
        size: int | None = None,
        source: str | None = None,
    ) -> OsTemplate:

        return OsTemplate(
            name=self._template_name(filename),
            filename=filename,
            distribution=(
                distribution
                or self._template_distribution(filename)
            ),
            version=(
                version
                or self._template_version(filename)
            ),
            architecture=self._template_architecture(filename),
            description=description,
            storage=storage,
            downloaded=downloaded,
            size=self._int_or_none(size),
            source=source,
        )

    def _template_name(
        self,
        filename: str,
    ) -> str:

        return (
            filename
            .removesuffix(".tar.zst")
            .removesuffix(".tar.xz")
            .removesuffix(".tar.gz")
        )

    def _template_distribution(
        self,
        filename: str,
    ) -> str | None:

        name = self._template_name(
            filename
        )
        parts = name.split("-")

        if not parts:
            return None

        return parts[0]

    def _template_version(
        self,
        filename: str,
    ) -> str | None:

        name = self._template_name(
            filename
        )
        parts = name.split("-")

        if len(parts) < 2:
            return None

        return parts[1]

    def _template_architecture(
        self,
        filename: str,
    ) -> str | None:

        name = self._template_name(
            filename
        )
        _, separator, architecture = name.rpartition("_")

        if not separator:
            return None

        return architecture

    def _template_filename(
        self,
        template: str | None,
    ) -> str:

        if not template:
            raise ProxmoxAPIError(
                "Missing template filename"
            )

        return template.rsplit("/", 1)[-1]

    def _template_storage(
        self,
        template: str,
    ) -> str:

        storage, separator, _ = template.partition(":")

        if not separator:
            raise ProxmoxAPIError(
                "Template reference must include storage"
            )

        return storage

    def _template_filename_from_line(
        self,
        line: str,
    ) -> str | None:

        parts = line.split()

        for part in reversed(parts):
            if self._looks_like_template_filename(part):
                return self._template_filename(part)

        return None

    def _template_volume_id_from_line(
        self,
        line: str,
    ) -> str | None:

        parts = line.split()

        for part in parts:
            if ":" in part and "vztmpl/" in part:
                return part

        return None

    def _template_size_from_line(
        self,
        line: str,
    ) -> int | None:

        parts = line.split()

        if len(parts) < 2:
            return None

        return self._size_to_bytes(
            parts[-1]
        )

    def _looks_like_template_filename(
        self,
        value: str,
    ) -> bool:

        return any(
            value.endswith(extension)
            for extension in (
                ".tar.zst",
                ".tar.xz",
                ".tar.gz",
            )
        )

    def _wait_for_task(
        self,
        task_id,
        timeout_seconds: int = 600,
    ):

        if not task_id:
            return

        for _ in range(timeout_seconds):
            status = self._node_api().tasks(str(task_id)).status.get()

            if status.get("status") == "stopped":
                if status.get("exitstatus") not in {
                    None,
                    "OK",
                }:
                    raise ProxmoxAPIError(
                        f"Proxmox task failed: {status.get('exitstatus')}"
                    )

                return

            sleep(1)

        raise ProxmoxAPIError(
            "Timed out waiting for Proxmox task"
        )

    def _network_bridge_from_data(
        self,
        data: dict[str, Any],
    ) -> NetworkBridge:

        return NetworkBridge(
            name=data.get("iface") or data.get("name"),
            active=self._proxmox_bool(
                data.get("active")
            ),
        )

    def _is_bridge_network(
        self,
        data: dict[str, Any],
    ) -> bool:

        network_type = data.get("type")

        return bool(
            data.get("iface") or data.get("name")
        ) and network_type in {
            None,
            "bridge",
            "OVSBridge",
        }

    def _proxmox_bool(
        self,
        value,
    ) -> bool:

        if isinstance(value, str):
            return value.lower() in {
                "1",
                "true",
                "yes",
                "on",
            }

        return bool(value)

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

    def _int_or_none(
        self,
        value,
    ) -> int | None:

        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _size_to_bytes(
        self,
        value: str,
    ) -> int | None:

        normalized = value.strip().upper()
        multipliers = {
            "K": 1024,
            "KB": 1024,
            "M": 1024 ** 2,
            "MB": 1024 ** 2,
            "G": 1024 ** 3,
            "GB": 1024 ** 3,
        }

        for suffix, multiplier in multipliers.items():
            if normalized.endswith(suffix):
                number = normalized.removesuffix(suffix)
                return int(float(number) * multiplier)

        return self._int_or_none(
            normalized
        )

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
