import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.core.dependencies import get_db, get_auth_service, get_container_service
from app.services.auth_service import AuthService
from app.services.container_service import ContainerService
from .console_manager import console_manager

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/api/console/{container_id}")
async def websocket_console_endpoint(
    websocket: WebSocket,
    container_id: str,
    db = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    container_service: ContainerService = Depends(get_container_service),
):
    # Aceitamos a conexão para poder validar o token e o container adequadamente
    await websocket.accept()

    # Tenta obter o token via query param
    token = websocket.query_params.get("token")

    # Fallback 1: Authorization Header
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:]

    # Fallback 2: Sec-WebSocket-Protocol
    if not token:
        protocol_header = websocket.headers.get("sec-websocket-protocol")
        if protocol_header:
            protocols = [p.strip() for p in protocol_header.split(",")]
            for p in protocols:
                if p.lower() != "bearer" and len(p) > 10:
                    token = p
                    break

    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    # Autenticação do usuário
    try:
        user = auth_service.get_authenticated_user(token)
    except Exception as e:
        await websocket.close(code=4002, reason="Invalid token")
        return

    # Verificação de existência do container
    try:
        container = container_service.get(container_id)
    except ValueError as e:
        logger.warning(f"Tentativa de console para container inexistente: {container_id}")
        await websocket.close(code=4003, reason="Container inexistente")
        return
    except Exception as e:
        logger.warning(f"Erro ao buscar container: {e}")
        await websocket.close(code=4003, reason="Container inexistente")
        return

    # Verificação de execução
    if container.status.lower() != "running":
        logger.warning(f"Tentativa de console para container parado: {container.name} (status={container.status})")
        await websocket.close(code=4004, reason="Container parado")
        return

    # Conexão válida
    logger.info(f"Conexão aberta para console: user={user.username}, container={container.name}")

    loop = asyncio.get_running_loop()
    # Chave única para o WebSocket atual para permitir conexões múltiplas concorrentes
    session_key = f"{container_id}_{user.id}_{id(websocket)}"
    
    session = console_manager.get_or_create_session(
        session_key,
        container.container_number,
        websocket,
        loop
    )

    try:
        session.start()

        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")

            if msg_type == "input":
                data = message.get("data", "")
                session.write(data)
            elif msg_type == "resize":
                cols = message.get("cols", 80)
                rows = message.get("rows", 24)
                session.resize(rows, cols)
            else:
                logger.warning(f"Unknown message type received: {msg_type}")

    except WebSocketDisconnect:
        # Apenas logamos quando fechar
        logger.info(f"Conexão encerrada para console: user={user.username}, container={container.name}")
    except Exception as e:
        logger.error(f"Erro na conexão do console WebSocket: {e}", exc_info=True)
    finally:
        # Garante o encerramento do processo PTY, filhos e descritores
        console_manager.remove_session(session_key)
