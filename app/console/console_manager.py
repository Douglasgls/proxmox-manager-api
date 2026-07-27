import logging
from typing import Dict
from .pty_session import PtySession

logger = logging.getLogger(__name__)


class ConsoleManager:
    def __init__(self):
        self.sessions: Dict[str, PtySession] = {}

    def get_or_create_session(self, session_key: str, container_number: int, websocket, loop) -> PtySession:
        if session_key in self.sessions:
            return self.sessions[session_key]

        session = PtySession(container_number, websocket, loop)
        self.sessions[session_key] = session
        return session

    def remove_session(self, session_key: str):
        if session_key in self.sessions:
            session = self.sessions.pop(session_key)
            session.close()

    def close_all_sessions(self):
        logger.info(f"Encerrando todas as {len(self.sessions)} sessões PTY ativas...")
        keys = list(self.sessions.keys())
        for key in keys:
            self.remove_session(key)
        logger.info("Todas as sessões PTY foram encerradas.")

    def cleanup_expired_sessions(self, timeout_seconds: int = 1800):
        expired_keys = [
            key for key, session in self.sessions.items()
            if session.is_expired(timeout_seconds)
        ]
        for key in expired_keys:
            logger.info(f"Purging expired PTY session: {key}")
            self.remove_session(key)


console_manager = ConsoleManager()
