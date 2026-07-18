import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.cloud import crypto
from app.cloud.dto import AgentRegistrationDTO
from app.cloud.manager import cloud_manager
from app.cloud.models import AgentSettings
from app.cloud.repository import AgentSettingsRepository
from app.database.session import SessionLocal

from dotenv import load_dotenv

load_dotenv()

router = APIRouter()


@router.post(
    "/cloud/register",
    summary="Registrar Environment Token",
    description=(
        "Recebe o Environment Token informado pelo usuário, "
        "criptografa e salva na tabela agent_settings. "
        "A partir deste momento a conexão com a Cloud é iniciada automaticamente."
    ),
)
async def register_agent(data: AgentRegistrationDTO):
    if not os.getenv("CLOUD_URL"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLOUD_URL is not configured.",
        )

    encrypted_token = crypto.encrypt(data.environment_token)

    with SessionLocal() as db:
        repository = AgentSettingsRepository(db)
        settings = repository.get()

        if settings:
            settings.environment_token_encrypted = encrypted_token
            settings.registered_at = datetime.now(timezone.utc)
            settings.jwt = settings.jwt
            settings.jwt_expires_at = settings.jwt_expires_at
            repository.update(settings)
        else:
            settings = AgentSettings(
                environment_token_encrypted=encrypted_token,
                registered_at=datetime.now(timezone.utc),
            )
            repository.save(settings)

    # Notificar o connection manager que o token foi registrado
    await cloud_manager.connection_manager.notify_registration()

    return {
        "status": "registered",
        "message": "Agent registered. Cloud connection starting...",
    }


@router.get(
    "/cloud/status",
    summary="Status da conexão com a Cloud",
)
def cloud_status():
    with SessionLocal() as db:
        repository = AgentSettingsRepository(db)
        settings = repository.get()

    if not settings:
        return {
            "registered": False,
            "connected": False,
            "message": "Agent not registered yet.",
        }

    connected = cloud_manager.connection_manager._ws_client.is_connected

    return {
        "registered": True,
        "connected": connected,
    }
