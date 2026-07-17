from fastapi import APIRouter, Depends, status, HTTPException
from app.core.dependencies import get_access_token_manager
from app.access.manager import AccessTokenManager
from app.access.dto import AccessTokenRevokeResponseDTO
from app.security.dependencies import get_current_user


router = APIRouter(dependencies=[Depends(get_current_user)])


@router.delete(
    "/{id}",
    response_model=AccessTokenRevokeResponseDTO,
)
def revoke_access_token(
    id: str,
    manager: AccessTokenManager = Depends(get_access_token_manager)
):
    revoked = manager.revoke_token(id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Access token not found",
        )
    
    return AccessTokenRevokeResponseDTO(message="Token successfully revoked")
