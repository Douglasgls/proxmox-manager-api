import logging

from app.cloud.auth_service import CloudAuthService
from app.cloud.connection_manager import CloudConnectionManager
from app.cloud.dispatcher import CloudDispatcher
from app.cloud.handlers.heartbeat import HeartbeatHandler
from app.cloud.handlers.system import SystemHandler
from app.cloud.websocket_client import CloudWebSocketClient

logger = logging.getLogger(__name__)


class CloudManager:
    """Fachada do módulo Cloud.

    Instancia todas as dependências e expõe start/stop.
    """

    def __init__(self) -> None:
        self._auth_service = CloudAuthService()
        self._ws_client = CloudWebSocketClient()
        self._dispatcher = CloudDispatcher()

        # Registrar handlers
        self._dispatcher.register("heartbeat", HeartbeatHandler.handle)
        self._dispatcher.register("system.info", SystemHandler.handle_info)

        self._connection_manager = CloudConnectionManager(
            auth_service=self._auth_service,
            ws_client=self._ws_client,
            dispatcher=self._dispatcher,
        )

    @property
    def connection_manager(self) -> CloudConnectionManager:
        return self._connection_manager

    async def start(self) -> None:
        """Inicia a comunicação com a Cloud."""

        logger.info("CloudManager starting...")
        await self._connection_manager.start()

    async def stop(self) -> None:
        """Encerra a comunicação com a Cloud."""

        logger.info("CloudManager stopping...")
        await self._connection_manager.stop()


# Singleton global
cloud_manager = CloudManager()
