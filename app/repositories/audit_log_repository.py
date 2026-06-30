from app.repositories.base_repository import BaseRepository

from app.models.audit_log import (
    AuditLog
)


class AuditLogRepository(
    BaseRepository[
        AuditLog
    ]
):

    def __init__(
        self,
        db
    ):
        super().__init__(
            db,
            AuditLog
        )


    def list_recent(
        self,
        limit=50
    ):

        return (
            self.db
            .query(
                AuditLog
            )
            .order_by(
                AuditLog.created_at.desc()
            )
            .limit(limit)
            .all()
        )
