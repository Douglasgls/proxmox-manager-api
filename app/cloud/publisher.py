import asyncio
import json
import logging
from app.core.event_bus import internal_event_bus, EnvironmentChanged

logger = logging.getLogger(__name__)


class EnvironmentChangedPublisher:
    """Publisher que escuta EnvironmentChanged e envia para a Cloud com debounce."""

    def __init__(self, connection_manager) -> None:
        self._connection_manager = connection_manager
        self._pending_task = None
        self.loop = None
        # Subscrever ao barramento de eventos interno
        internal_event_bus.subscribe(EnvironmentChanged, self.handle_environment_changed)

    def handle_environment_changed(self, event: EnvironmentChanged) -> None:
        """Trata o evento recebido, ignorando-o se já houver um agendamento pendente."""
        if self._pending_task is not None and not self._pending_task.done():
            logger.debug("EnvironmentChanged received, but debounce is active. Ignoring.")
            return

        current_loop = None
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if current_loop is not None and current_loop == self.loop:
            self._pending_task = current_loop.create_task(self._send_after_delay())
        elif self.loop and self.loop.is_running():
            self._pending_task = asyncio.run_coroutine_threadsafe(
                self._send_after_delay(),
                self.loop
            )
        elif current_loop is not None:
            self._pending_task = current_loop.create_task(self._send_after_delay())
        else:
            try:
                self._pending_task = asyncio.create_task(self._send_after_delay())
            except RuntimeError:
                logger.warning("No event loop available to schedule EnvironmentChanged dispatch.")

    async def _send_after_delay(self) -> None:
        try:
            logger.info("EnvironmentChanged received. Scheduling dispatch in 2 seconds (debounce)...")
            await asyncio.sleep(5.0)

            payload = {
                "origin": "agent",
                "type": "environment.changed",
                "payload": {}
            }
            logger.info("Sending environment.changed event to Cloud...")
            message_str = json.dumps(payload)
            print(f"\n[EVENT ENVIADO] Enviando evento de alteração ao Cloud: {message_str}\n")
            await self._connection_manager.send_message(message_str)
        except Exception as exc:
            logger.error("Failed to send environment.changed event: %s", exc)
        finally:
            self._pending_task = None
