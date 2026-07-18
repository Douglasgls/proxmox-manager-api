import logging
import platform
import socket
import time

from app.cloud.dto import CloudMessage
from app.cloud.dispatcher import SendFunc
from app.cloud.protocol import build_response

logger = logging.getLogger(__name__)

_AGENT_VERSION = "0.1.0"
_START_TIME = time.monotonic()


class SystemHandler:
    """Responde informações básicas do sistema para a Cloud."""

    @staticmethod
    async def handle_info(message: CloudMessage, send: SendFunc) -> None:
        uptime_seconds = int(time.monotonic() - _START_TIME)

        response = build_response(
            request_id=message.request_id,
            message_type="system.info.response",
            payload={
                "hostname": socket.gethostname(),
                "agent_version": _AGENT_VERSION,
                "uptime": uptime_seconds,
                "platform": platform.system(),
                "platform_version": platform.release(),
            },
        )
        await send(response)

        logger.debug("System info response sent")
