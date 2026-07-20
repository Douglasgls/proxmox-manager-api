import logging
from typing import Any

from app.services.job_service import JobService
from app.integrations.proxmox.container_session import ContainerSession
from app.tailscale.service import TailscaleService, TailscaleCommandError
from app.tailscale.repository import TailscaleRepository
from app.tailscale.model import TailscaleNode
from app.components.registry import ComponentRegistry
from app.components.definition import ComponentDefinition


logger = logging.getLogger(__name__)


class TailscaleManager:
    def __init__(
        self,
        job_service: JobService,
        container_session: ContainerSession,
        tailscale_service: TailscaleService,
        repository: TailscaleRepository,
    ):
        self.job_service = job_service
        self.container_session = container_session
        self.service = tailscale_service
        self.repository = repository

    def setup(self, job_id: int, container_id: str, proxmox_container_id: int):
        try:
            self.job_service.start(job_id)

            # Prepara o container para VPN (idempotente)
            vpn_result = self.container_session.proxmox_client.configure_container_for_vpn(
                proxmox_container_id
            )
            for msg in vpn_result.messages:
                self.job_service.update_progress(
                    job_id, 5, current_step=msg, output=f"[VPN Config] {msg}"
                )

            # Checking component
            self.job_service.update_progress(
                job_id, 10, current_step="Checking component", current_component="Tailscale"
            )
            is_installed = self.service.is_installed()

            if not is_installed:
                # Installing component
                self.job_service.update_progress(
                    job_id, 20, current_step="Installing component", output="Instalando tailscale via Component Framework..."
                )
                
                component_def = ComponentDefinition(name="tailscale")
                component = ComponentRegistry.get(component_def)
                
                install_output = component.install(self.container_session)
                self.job_service.update_progress(job_id, 30, output=install_output)
                
                # Validating installation
                self.job_service.update_progress(
                    job_id, 40, current_step="Validating installation", output="Validando instalação..."
                )
                val_output = component.validate(self.container_session)
                self.job_service.update_progress(job_id, 50, output=val_output)
            else:
                self.job_service.update_progress(
                    job_id, 50, output="Tailscale já está instalado."
                )

            # Starting tailscaled
            self.job_service.update_progress(
                job_id, 60, current_step="Starting tailscaled", output="Iniciando serviço tailscaled..."
            )
            start_result = self.service.start_service()
            self.job_service.update_progress(job_id, 65, output=f"systemctl start output: {start_result.stdout}")

            # Checking daemon
            self.job_service.update_progress(
                job_id, 70, current_step="Checking daemon", output="Verificando status do daemon..."
            )
            is_running = self.service.is_service_running()
            if not is_running:
                raise RuntimeError("O serviço tailscaled não está rodando após tentativa de iniciar.")
            
            self.job_service.update_progress(job_id, 75, output="Daemon tailscaled está ativo.")

            # Collecting information
            self.job_service.update_progress(
                job_id, 80, current_step="Collecting version"
            )
            version = self.service.get_version()

            self.job_service.update_progress(
                job_id, 85, current_step="Collecting machine id"
            )
            machine_id = self.service.get_machine_id()

            self.job_service.update_progress(
                job_id, 90, current_step="Collecting node key"
            )
            node_key = self.service.get_node_key()

            self.job_service.update_progress(
                job_id, 92, current_step="Collecting status"
            )
            tailscale_ip = self.service.get_ip()
            status_json = self.service.get_status_json()

            # Persisting database
            self.job_service.update_progress(
                job_id, 95, current_step="Persisting database", output="Salvando dados no banco..."
            )
            
            node = self.repository.get_by_container_id(container_id)
            if not node:
                node = TailscaleNode(
                    container_id=container_id,
                    proxmox_container_id=proxmox_container_id,
                )
            
            node.installed = True
            node.service_running = is_running
            node.version = version
            node.machine_id = machine_id
            node.node_key = node_key
            node.tailscale_ip = tailscale_ip
            node.status_json = status_json
            
            if node.id is None:
                self.repository.create(node)
            else:
                self.repository.update(node)

            try:
                from app.core.event_bus import internal_event_bus, EnvironmentChanged
                print("\n[EVENT ACTION] Setup do Tailscale concluído. Publicando EnvironmentChanged...\n")
                internal_event_bus.publish(EnvironmentChanged())
            except Exception as ev_exc:
                logger.error("Failed to publish EnvironmentChanged event after tailscale setup: %s", ev_exc)

            # Finished
            self.job_service.finish(job_id, output="Setup do Tailscale finalizado com sucesso.")

        except Exception as e:
            logger.exception("Falha no job de setup do tailscale")
            self.job_service.fail(job_id, str(e))
