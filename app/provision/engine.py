import logging
import re
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

    @staticmethod
    def _sanitize_cmd(cmd: str) -> str:
        if not cmd:
            return ""
        return re.sub(
            r'((?:PASSWORD|SECRET|KEY)=["\']?)([^"\'\s]+)(["\']?)',
            r'\1********\3',
            cmd,
            flags=re.IGNORECASE,
        )

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

        if plan.steps:
            for step in plan.steps:
                steps.append(step)
                try:
                    self._execute_step_commands(
                        step=step,
                        session=session,
                        on_component_install_start=on_component_install_start,
                        on_component_install_finish=on_component_install_finish,
                        on_component_validate_start=on_component_validate_start,
                        on_component_validate_finish=on_component_validate_finish,
                    )
                except Exception as error:
                    logger.exception(
                        "Erro ao provisionar passo: %s",
                        step.component_name,
                    )
                    step.fail(
                        finished_at=datetime.now(),
                        message=str(error),
                    )
                    return self._build_result(
                        success=False,
                        started_at=started_at,
                        steps=steps,
                        error=str(error),
                    )

        elif plan.components:
            for definition in plan.components:
                component = ComponentRegistry.get(definition)
                step = self._create_step(component)
                steps.append(step)
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
                    return self._build_result(
                        success=False,
                        started_at=started_at,
                        steps=steps,
                        error=str(error),
                    )

        return self._build_result(
            success=True,
            started_at=started_at,
            steps=steps,
        )

    def _execute_step_commands(
        self,
        step: ProvisionStep,
        session: ContainerSession,
        on_component_install_start: Callable[[ProvisionStep], None] | None = None,
        on_component_install_finish: Callable[[ProvisionStep], None] | None = None,
        on_component_validate_start: Callable[[ProvisionStep], None] | None = None,
        on_component_validate_finish: Callable[[ProvisionStep], None] | None = None,
    ):
        step.start(
            started_at=datetime.now(),
            message="Iniciando execução do passo.",
        )

        if on_component_install_start:
            on_component_install_start(step)

        for cmd in step.install_commands:
            logger.info("Executando instalação no container: %s", self._sanitize_cmd(cmd))
            res = session.exec(cmd, timeout=300)
            if res.exit_code != 0:
                raise Exception(
                    f"Erro executando comando de instalação '{self._sanitize_cmd(cmd)}':\n"
                    f"stdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
                )

        if on_component_install_finish:
            on_component_install_finish(step)

        if on_component_validate_start:
            on_component_validate_start(step)

        for cmd in step.validation_commands:
            logger.info("Executando validação no container: %s", self._sanitize_cmd(cmd))
            res = session.exec(cmd, timeout=60)
            if res.exit_code != 0:
                raise Exception(
                    f"Validação falhou para o comando '{self._sanitize_cmd(cmd)}':\n"
                    f"stdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
                )

        if on_component_validate_finish:
            on_component_validate_finish(step)

        step.finish(
            finished_at=datetime.now(),
            message="Passo executado com sucesso.",
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
            on_component_install_start(step)

        install_msg = None
        validate_msg = None

        if hasattr(component, "get_plan"):
            component_plan = component.get_plan()
            install_cmds = []
            validate_cmds = []
            
            # Extrai comandos dos passos do plano declarativo do componente
            for s in getattr(component_plan, "steps", []):
                install_cmds.extend(getattr(s, "install_commands", []))
                validate_cmds.extend(getattr(s, "validation_commands", []))

            # Executa comandos de instalação
            for cmd in install_cmds:
                logger.info("Executando instalação no container: %s", cmd)
                res = session.exec(cmd, timeout=300)
                if res.exit_code != 0:
                    raise Exception(
                        f"Erro executando comando de instalação '{cmd}':\n"
                        f"stdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
                    )
            install_msg = f"{len(install_cmds)} comandos de instalação executados com sucesso."

            if on_component_install_finish:
                on_component_install_finish(step)

            if on_component_validate_start:
                on_component_validate_start(step)

            # Executa comandos de validação
            for cmd in validate_cmds:
                logger.info("Executando validação no container: %s", cmd)
                res = session.exec(cmd, timeout=60)
                if res.exit_code != 0:
                    raise Exception(
                        f"Validação falhou para o comando '{cmd}':\n"
                        f"stdout:\n{res.stdout}\n\nstderr:\n{res.stderr}"
                    )
            validate_msg = f"{len(validate_cmds)} comandos de validação executados com sucesso."

            if on_component_validate_finish:
                on_component_validate_finish(step)
        else:
            # Fallback para componentes legado que executam diretamente
            if hasattr(component, "install"):
                install_msg = component.install(session=session)
            if on_component_install_finish:
                on_component_install_finish(step)
            if on_component_validate_start:
                on_component_validate_start(step)
            if hasattr(component, "validate"):
                validate_msg = component.validate(session=session)
            if on_component_validate_finish:
                on_component_validate_finish(step)

        step.finish(
            finished_at=datetime.now(),
            message=(
                validate_msg
                or install_msg
                or "Componente finalizado com sucesso."
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
