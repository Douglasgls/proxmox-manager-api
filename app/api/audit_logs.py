# from fastapi import APIRouter
# from fastapi import Depends

# from app.dto.request.audit_log import (
#     AuditLogDTO
# )

# from app.core.dependencies import (
#     get_audit_service
# )


# router = APIRouter()


# @router.post(
#     "/audit"
# )
# def create(
#     dto: AuditLogDTO,
#     service=Depends(
#         get_audit_service
#     )
# ):

#     return service.log(
#         entity=dto.entity_type,
#         entity_id=dto.entity_id,
#         action=dto.action,
#         details=dto.details
#     )
