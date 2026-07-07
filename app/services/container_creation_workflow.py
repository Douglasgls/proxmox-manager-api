import logging

from app.components.definition import ComponentDefinition
from app.dto.request.create_container import CreateContainerDTO
from app.provision.plan import ProvisionPlan
from app.services.container_service import ContainerService
from app.services.job_service import JobService


logger = logging.getLogger(__name__)


class ContainerCreationWorkflow:

    def __init__(
        self,
        container_service: ContainerService,
        job_service: JobService,
    ):
        self.container_service = container_service
        self.job_service = job_service

    def create_job(self):
        return self.job_service.create(
            job_type="container_create",
        )

    def run(
        self,
        job_id: str,
        dto: CreateContainerDTO,
    ):

        try:
            self.job_service.start(
                job_id
            )

            plan = self._build_provision_plan(
                dto
            )
            lifecycle_callbacks = self._build_lifecycle_callbacks(
                job_id=job_id,
            )
            callbacks = self._build_component_progress_tracker(
                job_id=job_id,
                plan=plan,
            )

            container = self.container_service.create(
                name=dto.name,
                password=dto.password,
                cpu=dto.cpu,
                memory_mb=dto.memory_mb,
                disk_gb=dto.disk_gb,
                image_name=dto.image_name,
                bridge=dto.bridge,
                ip_mode=dto.ip_mode,
                ip_address=dto.ip_address,
                cidr=dto.cidr,
                gateway=dto.gateway,
                firewall=dto.firewall,
                mtu=dto.mtu,
                vlan=dto.vlan,
                mac_address=dto.mac_address,
                provision_plan=plan,
                lifecycle_callbacks=lifecycle_callbacks,
                provision_callbacks=callbacks,
            )

            self.job_service.finish(
                job_id,
                output=f"Container {container.name} created.",
            )

        except Exception as exc:
            logger.exception(
                "Container creation workflow failed: %s",
                job_id,
            )
            self.job_service.fail(
                job_id,
                exc,
            )

    def _build_provision_plan(
        self,
        dto: CreateContainerDTO,
    ) -> ProvisionPlan:

        return ProvisionPlan(
            id="default",
            name="Default Provision",
            description="Provisionamento padrão",
            components=[
                ComponentDefinition(
                    name=component
                )
                for component in dto.components
            ],
        )

    def _update_job(
        self,
        job_id: str,
        progress: int,
        current_step: str,
        current_component: str | None = None,
        event: str = "job_updated",
        container_id: int | None = None,
        target_container: str | None = None,
    ):

        self.job_service.update_progress(
            job_id=job_id,
            progress=progress,
            current_step=current_step,
            current_component=current_component,
            event=event,
            container_id=container_id,
            target_container=target_container,
        )

    def _build_lifecycle_callbacks(
        self,
        job_id: str,
    ):

        def waiting_proxmox_task(_value):
            self._update_job(
                job_id=job_id,
                progress=15,
                current_step="Waiting Proxmox task",
                event="proxmox_task_waiting",
            )

        def container_created(proxmox_container):
            self._update_job(
                job_id=job_id,
                progress=25,
                current_step="Container created",
                container_id=proxmox_container.container_id,
                event="container_created",
            )

        def container_starting(_proxmox_container):
            self._update_job(
                job_id=job_id,
                progress=30,
                current_step="Starting container",
                event="container_starting",
            )

        def container_started(_proxmox_container):
            self._update_job(
                job_id=job_id,
                progress=35,
                current_step="Container started",
                event="container_started",
            )

        def container_persisted(container):
            self._update_job(
                job_id=job_id,
                progress=40,
                current_step="Container persisted",
                container_id=container.container_number,
                target_container=container.id,
            )

        def provisioning_started(_plan):
            self._update_job(
                job_id=job_id,
                progress=45,
                current_step="Provisioning components",
                event="provisioning_started",
            )

        return {
            "waiting_proxmox_task": waiting_proxmox_task,
            "container_created": container_created,
            "container_starting": container_starting,
            "container_started": container_started,
            "container_persisted": container_persisted,
            "provisioning_started": provisioning_started,
        }

    def _build_component_progress_tracker(
        self,
        job_id: str,
        plan: ProvisionPlan,
    ):
        component_count = max(
            len(plan.components),
            1,
        )
        total_units = component_count * 4
        progress_unit = max(
            int(50 / total_units),
            1,
        )
        state = {
            "unit": 0
        }

        def next_progress():
            state["unit"] += 1
            return min(
                45 + (state["unit"] * progress_unit),
                90,
            )

        def install_start(step):
            logger.info(
                "Installing %s...",
                step.component_name,
            )
            self._update_job(
                job_id=job_id,
                progress=next_progress(),
                current_step=f"Installing {step.component_name}",
                current_component=step.component_name,
                event="component_started",
            )

        def install_finish(step):
            logger.info(
                "Installed %s.",
                step.component_name,
            )
            self._update_job(
                job_id=job_id,
                progress=next_progress(),
                current_step=f"Installed {step.component_name}",
                current_component=step.component_name,
                event="component_install_finished",
            )

        def validate_start(step):
            logger.info(
                "Validating %s...",
                step.component_name,
            )
            self._update_job(
                job_id=job_id,
                progress=next_progress(),
                current_step=f"Validating {step.component_name}",
                current_component=step.component_name,
                event="component_validating",
            )

        def validate_finish(step):
            logger.info(
                "Validated %s.",
                step.component_name,
            )
            self._update_job(
                job_id=job_id,
                progress=next_progress(),
                current_step=f"Validated {step.component_name}",
                current_component=step.component_name,
                event="component_finished",
            )

        return {
            "install_start": install_start,
            "install_finish": install_finish,
            "validate_start": validate_start,
            "validate_finish": validate_finish,
        }
