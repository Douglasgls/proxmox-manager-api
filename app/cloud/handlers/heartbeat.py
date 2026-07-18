import logging

from app.cloud.dto import CloudMessage
from app.cloud.dispatcher import SendFunc
from app.cloud.protocol import build_response

logger = logging.getLogger(__name__)


class HeartbeatHandler:
    """Responde heartbeat da Cloud."""

    @staticmethod
    async def handle(message: CloudMessage, send: SendFunc) -> None:
        response = build_response(
            request_id=message.request_id,
            message_type="heartbeat.response",
        )
        await send(response)

        logger.debug("Heartbeat response sent")
