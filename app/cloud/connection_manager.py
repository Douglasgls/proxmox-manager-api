import asyncio
import logging
import os

from app.cloud.auth_service import CloudAuthService
from app.cloud.dispatcher import CloudDispatcher
from app.cloud.models import AgentSettings
from app.cloud.protocol import parse_message
from app.cloud.repository import AgentSettingsRepository
from app.cloud.websocket_client import CloudWebSocketClient
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)

_BACKOFF_STEPS = [5, 10, 30, 60]


class CloudConnectionManager:
    """Orquestrador principal da conexão Agent ↔ Cloud.

    Responsável por:
    - verificar/renovar JWT
    - abrir WebSocket
    - iniciar loop de escuta
    - reconectar automaticamente com backoff
    - detectar perda de conexão
    """

    def __init__(
        self,
        auth_service: CloudAuthService,
        ws_client: CloudWebSocketClient,
        dispatcher: CloudDispatcher,
    ) -> None:
        self._auth_service = auth_service
        self._ws_client = ws_client
        self._dispatcher = dispatcher
        self._running = False
        self._listen_task: asyncio.Task | None = None
        self._reconnect_attempt = 0

    async def start(self) -> None:
        """Ponto de entrada. Carrega settings, verifica JWT, conecta WS."""

        self._running = True

        settings = self._load_settings()

        if settings is None or not settings.environment_token_encrypted:
            logger.info(
                "Agent not registered yet. "
                "Waiting for Environment Token..."
            )
            return

        await self._connect_with_auth(settings)

    async def stop(self) -> None:
        """Para a conexão e o loop de escuta."""

        self._running = False

        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        await self._ws_client.close()
        logger.info("Cloud connection stopped")

    async def notify_registration(self) -> None:
        """Chamado quando o Environment Token é registrado.

        Se o manager já estiver rodando mas inativo (sem token),
        inicia a conexão.
        """

        if not self._running:
            return

        if self._ws_client.is_connected:
            return

        settings = self._load_settings()
        if settings and settings.environment_token_encrypted:
            logger.info("Environment Token registered. Starting connection...")
            await self._connect_with_auth(settings)

    async def _connect_with_auth(self, settings: AgentSettings) -> None:
        """Garante JWT válido e abre conexão WebSocket."""

        cloud_url = os.getenv("CLOUD_URL")
        if not cloud_url:
            logger.error("CLOUD_URL is not configured")
            return

        try:
            settings = await self._ensure_jwt(settings, cloud_url)
        except Exception as exc:
            logger.error("Authentication failed: %s", exc)
            self._schedule_reconnect()
            return

        try:
            ws_url = self._build_ws_url(cloud_url)
            await self._ws_client.connect(ws_url, settings.jwt)
            self._reconnect_attempt = 0
            self._listen_task = asyncio.create_task(self._listen_loop())
        except Exception as exc:
            logger.error("WebSocket connection failed: %s", exc)
            self._schedule_reconnect()

    async def _ensure_jwt(
        self,
        settings: AgentSettings,
        cloud_url: str,
    ) -> AgentSettings:
        """Verifica se o JWT está válido. Renova se expirado."""

        if settings.jwt and not self._auth_service.is_jwt_expired(settings.jwt_expires_at):
            logger.debug("JWT still valid")
            return settings

        logger.info("JWT expired or missing. Authenticating...")

        jwt_token, expires_at = await self._auth_service.renew_jwt(
            settings,
            cloud_url,
        )

        with SessionLocal() as db:
            repository = AgentSettingsRepository(db)
            current = repository.get()
            if current:
                current.jwt = jwt_token
                current.jwt_expires_at = expires_at
                repository.update(current)
                return current

        return settings

    async def _listen_loop(self) -> None:
        """Loop de recebimento de mensagens. Dispatch para handlers."""

        logger.info("Listen loop started")

        try:
            while self._running:
                try:
                    raw = await self._ws_client.receive()
                except Exception as exc:
                    if self._running:
                        logger.warning("WebSocket receive error: %s", exc)
                        await self._reconnect()
                    return

                message = parse_message(raw)
                if message is None:
                    continue

                await self._dispatcher.dispatch(
                    message,
                    self._ws_client.send,
                )

        except asyncio.CancelledError:
            logger.info("Listen loop cancelled")
        except Exception as exc:
            logger.error("Listen loop error: %s", exc)
            if self._running:
                await self._reconnect()

    async def _reconnect(self) -> None:
        """Lógica de reconexão com backoff exponencial."""

        await self._ws_client.close()

        if not self._running:
            return

        delay = self._get_backoff_delay()
        logger.info(
            "Reconnecting in %ds (attempt %d)...",
            delay,
            self._reconnect_attempt + 1,
        )

        await asyncio.sleep(delay)
        self._reconnect_attempt += 1

        settings = self._load_settings()
        if settings and settings.environment_token_encrypted:
            await self._connect_with_auth(settings)

    def _schedule_reconnect(self) -> None:
        """Agenda reconexão em background."""

        if self._running:
            asyncio.create_task(self._reconnect())

    def _get_backoff_delay(self) -> int:
        """Retorna o delay de backoff baseado no número de tentativas."""

        index = min(self._reconnect_attempt, len(_BACKOFF_STEPS) - 1)
        return _BACKOFF_STEPS[index]

    @staticmethod
    def _build_ws_url(cloud_url: str) -> str:
        """Converte URL HTTP para URL WebSocket."""

        base = cloud_url.rstrip("/")
        if base.startswith("https://"):
            return base.replace("https://", "wss://", 1) + "/ws/agent"
        else:
            return base.replace("http://", "ws://", 1) + "/ws/agent"

    @staticmethod
    def _load_settings() -> AgentSettings | None:
        """Carrega AgentSettings do banco (sessão pontual)."""

        with SessionLocal() as db:
            repository = AgentSettingsRepository(db)
            settings = repository.get()

            if settings:
                # Garantir que os atributos estejam carregados antes de fechar a sessão
                _ = settings.environment_token_encrypted
                _ = settings.jwt
                _ = settings.jwt_expires_at
                db.expunge(settings)

            return settings
