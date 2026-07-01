from dataclasses import replace

from app.core.exceptions import DomainValidationError
from app.integrations.proxmox import (
    ProxmoxClient,
)
from app.models.os_template import (
    OsTemplate,
)
from app.services.job_service import (
    JobService,
)


class TemplateService:

    def __init__(
        self,
        proxmox_client: ProxmoxClient,
        job_service: JobService,
    ):
        self.proxmox_client = proxmox_client
        self.job_service = job_service


    def list_available_templates(self) -> list[OsTemplate]:

        return (
            self.proxmox_client
            .list_available_templates()
        )


    def list_installed_templates(self) -> list[OsTemplate]:

        return (
            self.proxmox_client
            .list_installed_templates()
        )


    def download_template(
        self,
        storage: str,
        template: str,
    ):

        job = self.create_download_job(
            storage=storage,
            template=template,
        )

        return self.run_download_job(
            job_id=job.id,
            storage=storage,
            template=template,
        )


    def create_download_job(
        self,
        storage: str,
        template: str,
    ):

        self._validate_storage(
            storage
        )
        self._validate_template(
            template
        )
        self._ensure_template_available(
            template
        )

        return self.job_service.create(
            job_type="template_download",
        )


    def run_download_job(
        self,
        job_id: str,
        storage: str,
        template: str,
    ):

        try:
            self.job_service.start(
                job_id
            )
            self.job_service.update_progress(
                job_id,
                30,
            )

            result = (
                self.proxmox_client
                .download_template(
                    storage=storage,
                    template=template,
                )
            )

            self.job_service.update_progress(
                job_id,
                90,
            )

            return self.job_service.finish(
                job_id,
                output=result.message,
            )
        except Exception as exc:
            self.job_service.fail(
                job_id,
                exc,
            )
            raise


    def delete_template(
        self,
        template: str,
    ) -> OsTemplate:

        self._validate_template(
            template
        )
        installed_template = self._resolve_installed_template(
            template
        )
        volume_id = installed_template.volume_id

        if not volume_id:
            raise DomainValidationError(
                "Template instalado sem referência de storage"
            )

        (
            self.proxmox_client
            .delete_template(
                volume_id
            )
        )

        return replace(
            installed_template,
            downloaded=False,
            source="deleted",
        )


    def _ensure_template_available(
        self,
        template: str,
    ):

        if not self._find_available_template(
            template
        ):
            raise DomainValidationError(
                "Template não encontrado no catálogo disponível"
            )


    def _find_available_template(
        self,
        template: str,
    ) -> OsTemplate | None:

        for available_template in self.list_available_templates():
            if template in {
                available_template.filename,
                available_template.name,
            }:
                return available_template

        return None


    def _resolve_installed_template(
        self,
        template: str,
    ) -> OsTemplate:

        matches = [
            installed_template
            for installed_template in self.list_installed_templates()
            if template in self._installed_template_identifiers(
                installed_template
            )
        ]

        if not matches:
            raise DomainValidationError(
                "Template instalado não encontrado"
            )

        if len(matches) > 1:
            raise DomainValidationError(
                "Template ambíguo. Informe a referência completa com storage"
            )

        return matches[0]


    def _installed_template_identifiers(
        self,
        template: OsTemplate,
    ) -> set[str]:

        identifiers = {
            template.name,
            template.filename,
        }

        if template.volume_id:
            identifiers.add(
                template.volume_id
            )

        return identifiers


    def _validate_storage(
        self,
        storage: str,
    ):

        if not storage:
            raise DomainValidationError(
                "Storage é obrigatório"
            )


    def _validate_template(
        self,
        template: str,
    ):

        if not template:
            raise DomainValidationError(
                "Template é obrigatório"
            )


def run_template_download_job(
    job_id: str,
    storage: str,
    template: str,
):

    from app.database.session import SessionLocal
    from app.repositories.job_repository import JobRepository

    db = SessionLocal()

    try:
        service = TemplateService(
            ProxmoxClient(),
            JobService(
                JobRepository(db)
            ),
        )
        service.run_download_job(
            job_id=job_id,
            storage=storage,
            template=template,
        )
    except Exception:
        pass
    finally:
        db.close()
