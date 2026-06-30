# from fastapi import APIRouter
# from fastapi import Depends

# from app.dto.request.container_action import (
#     ContainerActionDTO
# )

# from app.core.dependencies import (
#     get_container_action_service
# )


# router = APIRouter()


# @router.post(
#     "/container-actions"
# )
# def create(
#     dto: ContainerActionDTO,
#     service=Depends(
#         get_container_action_service
#     )
# ):

#     return service.register(
#         dto.container_id,
#         dto.action,
#         dto.status
#     )