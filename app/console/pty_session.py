import os
import pty
import struct
import fcntl
import termios
import signal
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

    def start(self):
        self.active = True
        try:
            self.pid, self.fd = pty.fork()
        except Exception as e:
            logger.error(f"Erro na criação da PTY para o container {self.container_number}: {e}")
            raise e

        if self.pid == 0:
            # Processo filho
            try:
                # Configura variáveis básicas de ambiente para emulação de terminal
                os.environ["TERM"] = "xterm-256color"
                os.environ["HOME"] = "/root"
                
                # Tenta executar com bash; se falhar, executa sh
                cmd = ["pct", "exec", str(self.container_number), "--", "sh", "-c", 
                       "if command -v bash >/dev/null 2>&1; then exec bash; else exec sh; fi"]
                
                os.execvp(cmd[0], cmd)
            except Exception:
                os._exit(1)
        else:
            # Processo pai
            logger.info(f"Sessão PTY iniciada para o container {self.container_number} com PID {self.pid}")
            
            # Executa a leitura do descritor de arquivo em uma thread separada para não bloquear o loop do asyncio
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()

    def _read_loop(self):
        buffer_size = 4096
        while self.active and self.fd is not None:
            try:
                data = os.read(self.fd, buffer_size)
                if not data:
                    break
                
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
                os.write(self.fd, data.encode('utf-8'))
            except Exception as e:
                logger.error(f"Erro ao escrever na PTY: {e}")

    def resize(self, rows: int, cols: int):
        if self.fd is not None:
            try:
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
            try:
                os.kill(self.pid, signal.SIGTERM)
                os.waitpid(self.pid, os.WNOHANG)
            except Exception:
                pass
            self.pid = None
