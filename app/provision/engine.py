import logging
from datetime import datetime
from collections.abc import Callable

from app.components import definition
from app.components.base_components import BaseComponent
from app.integrations.proxmox.container_session import ContainerSession
from app.provision.plan import ProvisionPlan
from app.provision.result import ProvisionResult
from app.provision.step import ProvisionStep

from app.components.registry import ComponentRegistry


logger = logging.getLogger(__name__)


class ProvisionEngine:
    def __init__(self):
        ...

    def execute(
        self,
        plan: ProvisionPlan,
        session: ContainerSession,
        on_component_install_start: Callable[[ProvisionStep], None] | None = None,
        on_component_install_finish: Callable[[ProvisionStep], None] | None = None,
        on_component_validate_start: Callable[[ProvisionStep], None] | None = None,
        on_component_validate_finish: Callable[[ProvisionStep], None] | None = None,
    ) -> ProvisionResult:
        started_at = datetime.now()
        steps: list[ProvisionStep] = []

        logger.info(
            "Iniciando provisionamento: %s",
            plan.name,
        )

        for definition in plan.components:
            component = ComponentRegistry.get(definition)
        
            step = self._create_step(
                component
            )

            steps.append(
                step
            )

            try:
                self._execute_component(
                    component=component,
                    session=session,
                    step=step,
                    on_component_install_start=on_component_install_start,
                    on_component_install_finish=on_component_install_finish,
                    on_component_validate_start=on_component_validate_start,
                    on_component_validate_finish=on_component_validate_finish,
                )

            except Exception as error:
                logger.exception(
                    "Erro ao provisionar componente: %s",
                    step.component_name,
                )

                step.fail(
                    finished_at=datetime.now(),
                    message=str(error),
                )

                # TODO: atualizar o Job como falho quando o framework for integrado ao sistema de Jobs.
                return self._build_result(
                    success=False,
                    started_at=started_at,
                    steps=steps,
                    error=str(error),
                )

        # TODO: atualizar o Job como concluido quando o framework for integrado ao sistema de Jobs.
        return self._build_result(
            success=True,
            started_at=started_at,
            steps=steps,
        )

    def _execute_component(
        self,
        component: BaseComponent,
        session: ContainerSession,
        step: ProvisionStep,
        on_component_install_start: Callable[[ProvisionStep], None] | None = None,
        on_component_install_finish: Callable[[ProvisionStep], None] | None = None,
        on_component_validate_start: Callable[[ProvisionStep], None] | None = None,
        on_component_validate_finish: Callable[[ProvisionStep], None] | None = None,
    ):
        step.start(
            started_at=datetime.now(),
            message="Iniciando componente.",
        )

        if on_component_install_start:
            on_component_install_start(
                step
            )

        install_message =component.install(
        session=session,
        )

        if on_component_install_finish:
            on_component_install_finish(
                step
            )

        if on_component_validate_start:
            on_component_validate_start(
                step
            )
        
        validate_message = component.validate(
            session=session
        )

        if on_component_validate_finish:
            on_component_validate_finish(
                step
            )

        step.finish(
            finished_at=datetime.now(),
            message=(
                validate_message
                or install_message
                or "Componente finalizado."
            ),
        )

        logger.info(
            "Componente provisionado com sucesso: %s",
            step.component_name,
        )

    def _create_step(
        self,
        component: BaseComponent,
    ) -> ProvisionStep:
        return ProvisionStep(
            component_name=component.name,
        )

    def _build_result(
        self,
        success: bool,
        started_at: datetime,
        steps: list[ProvisionStep],
        error: str | None = None,
    ) -> ProvisionResult:
        finished_at = datetime.now()

        return ProvisionResult(
            success=success,
            started_at=started_at,
            finished_at=finished_at,
            duration=(
                finished_at
                -
                started_at
            ).total_seconds(),
            steps=steps,
            error=error,
        )
