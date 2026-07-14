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

console_manager = ConsoleManager()
