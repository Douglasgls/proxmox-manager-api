import logging

from app.cloud.dto import CloudMessage
from app.cloud.dispatcher import SendFunc
from app.cloud.protocol import build_response, build_error
from app.cloud.sync_service import EnvironmentSyncService
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)


class EnvironmentSyncHandler:
    """Handler responsável por tratar solicitações de sincronização de ambiente (environment.sync)."""

    @staticmethod
    async def handle_sync(message: CloudMessage, send: SendFunc) -> None:
        logger.info("Received environment.sync request from Cloud (request_id=%s)", message.request_id)

        try:
            with SessionLocal() as db:
                sync_service = EnvironmentSyncService(db)
                snapshot = sync_service.get_public_environment_snapshot()

            # Converter para dict e enviar via WebSocket seguindo o envelope do protocolo
            # Sem passar o message_type para omitir a chave "type" no envelope de resposta do protocolo,
            # respeitando exatamente a especificação de resposta do WEBSOCKET_PROTOCOL.md.
            response = build_response(
                request_id=message.request_id,
                payload=snapshot.model_dump(),
            )
            await send(response)
            logger.info("Environment sync snapshot successfully sent to Cloud")

        except Exception as exc:
            logger.error("Failed to perform environment sync: %s", exc, exc_info=True)
            err = build_error(
                request_id=message.request_id,
                code="INTERNAL_ERROR",
                message="Internal error occurred while preparing environment sync snapshot.",
            )
            await send(err)
