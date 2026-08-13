import logging

from app.dto.request.create_container import InstallContainerComponentsDTO
from app.dto.response.job import JobCreatedResponseDTO
from app.integrations.proxmox import ContainerSession, ProxmoxClient
from app.repositories.container_repository import ContainerRepository
from app.services.component_service import ComponentService
from app.services.container_component_service import ContainerComponentService
from app.services.job_service import JobService

logger = logging.getLogger(__name__)


class ContainerComponentInstallWorkflow:

    def __init__(
        self,
        container_repository: ContainerRepository,
        component_service: ComponentService,
        container_component_service: ContainerComponentService,
        job_service: JobService,
        proxmox_client: ProxmoxClient | None = None,
    ):
        self.container_repository = container_repository
        self.component_service = component_service
        self.container_component_service = container_component_service
        self.job_service = job_service
        self.proxmox_client = proxmox_client or ProxmoxClient()

    def create_job(self, container_id: str) -> JobCreatedResponseDTO:
        container = self.container_repository.get(container_id)
        if not container:
            raise ValueError("Container não encontrado")

        job = self.job_service.create(
            job_type="container_install_components",
            target=container_id,
        )
        return JobCreatedResponseDTO(job_id=job.id)

    def run(
        self,
        job_id: str,
        container_id: str,
        dto: InstallContainerComponentsDTO,
    ):
        try:
            self.job_service.start(job_id)

            container = self.container_repository.get(container_id)
            if not container:
                raise ValueError(f"Container {container_id} não encontrado")

            # Resolve os componentes válidos
            resolved_components = self.component_service.validate_and_resolve_slugs(dto.components)

            # Instancia a sessão do Proxmox para o container
            session = ContainerSession(
                proxmox_client=self.proxmox_client,
                container_id=container.container_number,
            )

            # Cria registros PENDING no banco e executa os planos através do ProvisionEngine
            self.container_component_service.create_pending_records(
                container_id=container.id,
                components=resolved_components,
            )

            results = self.container_component_service.provision_container_components(
                container=container,
                components=resolved_components,
                session=session,
            )

            failed = [r for r in results if str(r.status) == "FAILED"]
            if failed:
                err_msg = failed[0].error or "Falha durante o provisionamento dos componentes"
                raise RuntimeError(err_msg)

            self.job_service.finish(
                job_id,
                output=f"Componentes instalados com sucesso no container {container.name}",
            )

        except Exception as exc:
            logger.exception(
                "Falha ao instalar componentes no container %s (Job: %s)",
                container_id,
                job_id,
            )
            self.job_service.fail(
                job_id,
                exc,
            )
