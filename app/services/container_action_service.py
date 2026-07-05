# from app.models.container_action import (
#     ContainerAction
# )
# from app.repositories.container_action_repository import ( 
#     ContainerActionRepository
# )   

# class ContainerActionService:

#     def __init__(
#         self,
#         repository: ContainerActionRepository
#     ):
#         self.repository = repository


#     def register(
#         self,
#         container_id,
#         action,
#         status
#     ):

#         obj = (
#             ContainerAction(
#                 container_id=
#                 container_id,

#                 action=
#                 action,

#                 status=
#                 status
#             )
#         )

#         return (
#             self.repository
#             .create(
#                 obj
#             )
#         )