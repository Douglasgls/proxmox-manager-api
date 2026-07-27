import os
import pty
import struct
import fcntl
import termios
import signal
import time
import threading
import logging
import asyncio
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class PtySession:
    def __init__(self, container_number: int, websocket: WebSocket, loop: asyncio.AbstractEventLoop):
        self.container_number = container_number
        self.websocket = websocket
        self.loop = loop
        self.fd = None
        self.pid = None
        self.active = False
        self.thread = None
        self.last_activity = time.time()

    def touch(self):
        self.last_activity = time.time()

    def is_expired(self, timeout_seconds: int = 1800) -> bool:
        return (time.time() - self.last_activity) > timeout_seconds

    def start(self):
        self.active = True
        self.touch()
        try:
            self.pid, self.fd = pty.fork()
        except Exception as e:
            logger.error(f"Erro na criação da PTY para o container {self.container_number}: {e}")
            raise e

        if self.pid == 0:
            # Processo filho
            try:
                cmd = [
                    "pct",
                    "exec",
                    str(self.container_number),
                    "--",
                    "env",
                    "TERM=xterm-256color",
                    "LANG=C.UTF-8",
                    "LC_ALL=C.UTF-8",
                    "HOME=/root",
                    "sh",
                    "-c",
                    "if command -v bash >/dev/null 2>&1; then exec bash; else exec sh; fi"
                ]
                os.execvp(cmd[0], cmd)
            except Exception:
                os._exit(1)
        else:
            # Processo pai
            logger.info(f"Sessão PTY iniciada para o container {self.container_number} com PID {self.pid}")
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()

    def _read_loop(self):
        buffer_size = 4096
        while self.active and self.fd is not None:
            try:
                data = os.read(self.fd, buffer_size)
                if not data:
                    break
                
                self.touch()
                text = data.decode('utf-8', errors='ignore')
                
                if self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self.websocket.send_json({"type": "output", "data": text}),
                        self.loop
                    )
            except OSError:
                # EIO é lançado normalmente quando o processo filho encerra
                break
            except Exception as e:
                logger.error(f"Erro ao ler do descritor PTY: {e}")
                break
                
        if self.active:
            asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop)

    def write(self, data: str):
        if self.fd is not None:
            try:
                self.touch()
                os.write(self.fd, data.encode('utf-8'))
            except Exception as e:
                logger.error(f"Erro ao escrever na PTY: {e}")

    def resize(self, rows: int, cols: int):
        if self.fd is not None:
            try:
                self.touch()
                s = struct.pack('HHHH', rows, cols, 0, 0)
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ, s)
            except Exception as e:
                logger.error(f"Erro ao redimensionar a PTY: {e}")

    def close(self):
        if not self.active:
            return
            
        self.active = False
        
        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
            self.fd = None

        if self.pid is not None:
            pid = self.pid
            self.pid = None
            try:
                logger.info(f"Encerrando processo PTY PID {pid}...")
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.1)
                
                # Checar se encerrou graciosamente
                res, _ = os.waitpid(pid, os.WNOHANG)
                if res == 0:
                    logger.warning(f"Processo PTY PID {pid} não respondeu ao SIGTERM. Enviando SIGKILL...")
                    os.kill(pid, signal.SIGKILL)
                    os.waitpid(pid, 0)
                logger.info(f"Processo PTY PID {pid} encerrado com sucesso.")
            except ProcessLookupError:
                pass
            except Exception as exc:
                logger.error(f"Erro ao matar processo PTY PID {pid}: {exc}")
