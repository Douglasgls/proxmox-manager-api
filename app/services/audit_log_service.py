from app.models.audit_log import (
    AuditLog
)
from app.repositories.audit_log_repository import ( 
    AuditLogRepository
)


class AuditLogService:

    def __init__(
        self,
        repository: AuditLogRepository
    ):
        self.repository = repository


    def log(
        self,
        entity,
        action,
        entity_id=None,
        details=None
    ):

        log = AuditLog(
            entity_type=entity,
            entity_id=entity_id,
            action=action,
            details=details
        )

        return (
            self.repository
            .create(
                log
            )
        )
