import logging
from typing import Awaitable, Callable

from app.cloud.dto import CloudMessage

logger = logging.getLogger(__name__)

# Tipo de um handler: recebe a mensagem e uma função para enviar resposta
SendFunc = Callable[[str], Awaitable[None]]
HandlerFunc = Callable[[CloudMessage, SendFunc], Awaitable[None]]


class CloudDispatcher:
    """Dispatch de mensagens da Cloud para handlers registrados.

    Sem if/else. Dicionário de handlers indexados por message type.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, HandlerFunc] = {}

    def register(self, message_type: str, handler: HandlerFunc) -> None:
        """Registra um handler para um tipo de mensagem."""

        self._handlers[message_type] = handler
        logger.info("Handler registered: %s", message_type)

    async def dispatch(
        self,
        message: CloudMessage,
        send: SendFunc,
    ) -> None:
        """Busca o handler pelo type da mensagem e invoca."""

        if message.success is False or message.error:
            err_msg = message.error.get("message") if isinstance(message.error, dict) else str(message.error or "Unknown error")
            err_code = message.error.get("code") if isinstance(message.error, dict) else "ERROR"
            print(f"\n❌ [RESPOSTA DE ERRO DA CLOUD] A Cloud respondeu com erro para a requisição '{message.request_id}': [{err_code}] {err_msg}\n")
            logger.error("Cloud returned error (request_id=%s, code=%s): %s", message.request_id, err_code, err_msg)
            return

        if not message.type:
            logger.warning("Received message without type or handler: %s", message)
            return

        handler = self._handlers.get(message.type)

        if handler:
            await handler(message, send)
        else:
            logger.warning(
                "No handler registered for message type: %s",
                message.type,
            )
