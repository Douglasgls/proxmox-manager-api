import logging

import websockets
from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)


class CloudWebSocketClient:
    """Cliente WebSocket puro para comunicação com a Cloud.

    Responsável apenas por:
    - abrir conexão
    - enviar mensagem
    - receber mensagem
    - fechar conexão

    Nenhuma regra de negócio.
    """

    def __init__(self) -> None:
        self._connection: ClientConnection | None = None

    @property
    def is_connected(self) -> bool:
        return self._connection is not None and self._connection.protocol.state.name == "OPEN"

    async def connect(self, url: str, token: str) -> None:
        """Abre conexão WebSocket com a Cloud."""

        ws_url = f"{url}?token={token}"

        logger.info("Connecting to Cloud WebSocket: %s", url)

        self._connection = await websockets.connect(
            ws_url,
            open_timeout=15,
            close_timeout=10,
        )

        logger.info("WebSocket connection established")

    async def send(self, message: str) -> None:
        """Envia uma mensagem pela conexão WebSocket."""

        if not self._connection:
            raise RuntimeError("WebSocket not connected")

        await self._connection.send(message)

    async def receive(self) -> str:
        """Recebe uma mensagem da conexão WebSocket (blocking async)."""

        if not self._connection:
            raise RuntimeError("WebSocket not connected")

        message = await self._connection.recv()
        return str(message)

    async def close(self) -> None:
        """Fecha a conexão WebSocket."""

        if self._connection:
            try:
                await self._connection.close()
            except Exception as exc:
                logger.warning("Error closing WebSocket: %s", exc)
            finally:
                self._connection = None
