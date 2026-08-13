import logging
from typing import Any
from app.components.registry import ComponentRegistry
from app.integrations.proxmox.container_session import ContainerSession
from app.models.component import Component
from app.models.container import Container
from app.models.container_component import ContainerComponent, ContainerComponentStatus
from app.provision.engine import ProvisionEngine
from app.repositories.container_component_repository import ContainerComponentRepository

logger = logging.getLogger(__name__)


class ContainerComponentService:
    """Serviço dedicado à orquestração dos componentes instalados em um container específico."""

    def __init__(
        self,
        repository: ContainerComponentRepository,
        provision_engine: ProvisionEngine | None = None,
    ):
        self.repository = repository
        self.provision_engine = provision_engine or ProvisionEngine()

    def create_pending_records(
        self,
        container_id: str,
        components: list[Component],
    ) -> list[ContainerComponent]:
        """Cria os registros iniciais com status PENDING na tabela container_components."""
        records = []
        for comp in components:
            cfg = getattr(comp, "_request_config", None)
            record = self.repository.create_pending_record(
                container_id=container_id,
                component_id=comp.id,
                config=cfg,
            )
            records.append(record)
        return records

    def provision_container_components(
        self,
        container: Container,
        components: list[Component],
        session: ContainerSession,
        callbacks: dict[str, Any] | None = None,
    ) -> list[ContainerComponent]:
        """Executa o provisionamento sequencial dos componentes no container via ProvisionEngine.
        
        Garante a rastreabilidade PENDING -> INSTALLING -> INSTALLED / FAILED e a preservação
        exata do estado em caso de falha parcial.
        """
        callbacks = callbacks or {}
        results = []

        for comp in components:
            request_cfg = getattr(comp, "_request_config", None)
            record = self.repository.get_by_container_and_component(
                container_id=container.id,
                component_id=comp.id,
            )
            if not record:
                record = self.repository.create_pending_record(
                    container_id=container.id,
                    component_id=comp.id,
                    config=request_cfg,
                )

            logger.info(
                "Iniciando instalação do componente %s (slug: %s) no container %s",
                comp.name,
                comp.slug,
                container.container_number,
            )

            # Transição PENDING -> INSTALLING
            record = self.repository.update_status(
                container_component=record,
                status=ContainerComponentStatus.INSTALLING.value,
                config=request_cfg,
            )

            try:
                impl = ComponentRegistry.get(comp.slug, config=request_cfg)
                plan = impl.get_plan()

                provision_result = self.provision_engine.execute(
                    plan=plan,
                    session=session,
                    on_component_install_start=callbacks.get("install_start"),
                    on_component_install_finish=callbacks.get("install_finish"),
                    on_component_validate_start=callbacks.get("validate_start"),
                    on_component_validate_finish=callbacks.get("validate_finish"),
                )

                if provision_result.success:
                    installed_version = impl.metadata().get("version")
                    effective_config = getattr(impl, "get_effective_config", lambda: request_cfg)()
                    logger.info(
                        "Componente %s instalado com sucesso no container %s (versão: %s)",
                        comp.slug,
                        container.container_number,
                        installed_version,
                    )
                    record = self.repository.update_status(
                        container_component=record,
                        status=ContainerComponentStatus.INSTALLED.value,
                        installed_version=installed_version,
                        config=effective_config,
                    )
                    results.append(record)
                else:
                    error_msg = provision_result.error or "Falha genérica no provisionamento"
                    logger.error(
                        "Falha ao provisionar componente %s no container %s: %s",
                        comp.slug,
                        container.container_number,
                        error_msg,
                    )
                    record = self.repository.update_status(
                        container_component=record,
                        status=ContainerComponentStatus.FAILED.value,
                        error=error_msg,
                    )
                    results.append(record)
                    break

            except Exception as exc:
                error_msg = str(exc)
                logger.exception(
                    "Exceção durante instalação do componente %s no container %s: %s",
                    comp.slug,
                    container.container_number,
                    error_msg,
                )
                record = self.repository.update_status(
                    container_component=record,
                    status=ContainerComponentStatus.FAILED.value,
                    error=error_msg,
                )
                results.append(record)
                break

        return results
