from fastapi import Depends

from app.database.session import SessionLocal


from app.repositories.user_repository import (
    UserRepository
)

from app.repositories.container_repository import (
    ContainerRepository
)

from app.repositories.job_repository import (
    JobRepository
)

from app.repositories.container_action_repository import (
    ContainerActionRepository
)

from app.repositories.audit_log_repository import (
    AuditLogRepository
)

from app.integrations.proxmox import (
    ProxmoxClient
)
from app.provision.engine import ProvisionEngine


from app.services.user_service import (
    UserService
)

from app.services.container_service import (
    ContainerService
)

from app.services.container_creation_workflow import (
    ContainerCreationWorkflow
)

from app.services.job_service import (
    JobService
)

from app.services.template_service import (
    TemplateService
)

# from app.services.container_action_service import (
#     ContainerActionService
# )

from app.services.audit_log_service import (
    AuditLogService
)


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


def get_proxmox_client():

    return ProxmoxClient()


def get_provision_engine():

    return ProvisionEngine()


def get_user_service(db=Depends(get_db)):

    return UserService(
        UserRepository(db)
    )


def get_container_service(
    db=Depends(get_db),
    provision_engine=Depends(get_provision_engine),
):

    return ContainerService(
        repository=ContainerRepository(db),
        proxmox_client=ProxmoxClient(),
        audit_log_service=AuditLogService(
            AuditLogRepository(db)
        ),
        provision_engine=provision_engine,
    )


def get_job_service(db=Depends(get_db)):

    return JobService(
        JobRepository(db)
    )


def get_container_creation_workflow(
    container_service=Depends(get_container_service),
    job_service=Depends(get_job_service),
):

    return ContainerCreationWorkflow(
        container_service=container_service,
        job_service=job_service,
    )


def get_template_service(db=Depends(get_db)):

    return TemplateService(
        ProxmoxClient(),
        JobService(
            JobRepository(db)
        )
    )


# def get_container_action_service(
#     db=Depends(get_db)
# ):

#     return ContainerActionService(
#         ContainerActionRepository(
#             db
#         )
#     )


def get_audit_service(
    db=Depends(get_db)
):

    return AuditLogService(
        AuditLogRepository(db)
    )
