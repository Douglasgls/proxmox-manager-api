# Depois eu vejo se precisa disso.
# from app.api.audit_logs import router as audit
# from app.api.container_actions import router as actions


from contextlib import asynccontextmanager
import asyncio
import os
from fastapi import APIRouter, FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import logging
from app.api.users import router as users
from app.api.auth import router as auth
from app.api.containers import router as containers
from app.api.jobs import router as jobs
from app.api.templates import router as templates
from app.api.health import router as health
from app.api.monitoring import router as monitoring
from app.api.websocket import router as websocket
from app.api.access_tokens import router as access_tokens
from app.api.components import router as components
from app.api.cloud import router as cloud_router
from app.api.agent import router as agent_router
from app.console.websocket_console import router as console_router
from app.console.console_manager import console_manager
from app.core.exceptions import AuthenticationError, DomainValidationError
from app.services.monitoring.tasks.adapter import metrics_collector
from app.services.job_events import job_event_manager
from app.cloud.manager import cloud_manager
from app.database.session import SessionLocal
from app.repositories.container_repository import ContainerRepository
from app.integrations.proxmox import (
    ContainerNotFoundError,
    ProxmoxAPIError,
    ProxmoxClient,
    ProxmoxConnectionError,
    ProxmoxPermissionError,
)
from app.services.container_service import ContainerService
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_event_manager.loop = asyncio.get_running_loop()
    print(f"[Lifespan DEBUG] Registrou o event loop principal no job_event_manager: {job_event_manager.loop}")
    
    # 0. Sincronização idempotente do catálogo de componentes padrão
    try:
        from app.repositories.component_repository import ComponentRepository
        from app.services.component_service import ComponentService
        with SessionLocal() as db:
            comp_service = ComponentService(ComponentRepository(db))
            comp_service.sync_default_catalog()
            logger.info("Catálogo de componentes padrão sincronizado com sucesso.")
    except Exception as seed_exc:
        logger.error("Erro ao sincronizar catálogo de componentes padrão: %s", seed_exc, exc_info=True)

    # 1. Boot do Agent Config
    try:
        from app.repositories.agent_config_repository import AgentConfigRepository
        from app.services.agent_config_service import AgentConfigService
        with SessionLocal() as db:
            agent_config_service = AgentConfigService(AgentConfigRepository(db))
            agent_config_service.bootstrap_from_env()
            config = agent_config_service.get_config()
            app.state.proxmox_configured = config.configured
            logger.info("Agent configurado com Proxmox: %s", app.state.proxmox_configured)
    except Exception as exc:
        logger.error("Erro ao realizar bootstrap da configuração do Agent: %s", exc, exc_info=True)
        app.state.proxmox_configured = False

    # 2. Reconciliação atômica e métricas (condicionais ao Proxmox)
    reconciliation_success = False
    task = None
    if app.state.proxmox_configured:
        max_retries = 3
        from app.core.dependencies import get_proxmox_client
        for attempt in range(1, max_retries + 1):
            try:
                logger.info("Iniciando reconciliação inicial dos containers com Proxmox VE (tentativa %d/%d)...", attempt, max_retries)
                with SessionLocal() as db:
                    agent_config_service = AgentConfigService(AgentConfigRepository(db))
                    proxmox_client = get_proxmox_client(agent_config_service)
                    service = ContainerService(
                        repository=ContainerRepository(db),
                        proxmox_client=proxmox_client,
                    )
                    await asyncio.to_thread(service.sync_all)
                reconciliation_success = True
                logger.info("Reconciliação inicial com Proxmox VE concluída com sucesso.")
                break
            except Exception as exc:
                logger.error("Erro na tentativa %d de reconciliação com Proxmox VE: %s", attempt, exc, exc_info=True)
                if attempt < max_retries:
                    await asyncio.sleep(2)
        
        task = asyncio.create_task(metrics_collector.start())
    else:
        logger.warning("Proxmox não configurado. Pulando reconciliação e métricas de host/container.")

    app.state.is_reconciled = reconciliation_success

    # 3. Iniciar gerenciador do Cloud
    logger.info("Iniciando conexão e sincronização com o Cloud Control Plane...")
    await cloud_manager.start()
    
    yield

    # Encerramento gracioso de serviços
    logger.info("Encerrando serviços do Agent...")
    console_manager.close_all_sessions()
    await cloud_manager.stop()
    await metrics_collector.stop()
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(DomainValidationError)
def domain_validation_error_handler(
    _request: Request,
    exc: DomainValidationError,
):
    return JSONResponse(
        status_code=400,
        content={
            "detail": str(exc)
        },
    )


@app.exception_handler(ValueError)
def value_error_handler(
    _request: Request,
    exc: ValueError,
):
    return JSONResponse(
        status_code=400,
        content={
            "detail": str(exc)
        },
    )


@app.exception_handler(AuthenticationError)
def authentication_error_handler(
    _request: Request,
    exc: AuthenticationError,
):
    return JSONResponse(
        status_code=401,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(ProxmoxPermissionError)
def proxmox_permission_error_handler(
    _request: Request,
    exc: ProxmoxPermissionError,
):
    detail_msg = "Permissão insuficiente no Proxmox VE."
    if exc.required_permission and exc.path:
        detail_msg = f"Permissão insuficiente no Proxmox VE: privilégio '{exc.required_permission}' necessário no caminho '{exc.path}'."
    elif exc.required_permission:
        detail_msg = f"Permissão insuficiente no Proxmox VE: privilégio '{exc.required_permission}' necessário."

    logger.warning("Proxmox permission denied: %s (path=%s, perm=%s)", exc.message, exc.path, exc.required_permission)

    return JSONResponse(
        status_code=403,
        content={
            "detail": detail_msg,
            "error_code": "PROXMOX_PERMISSION_DENIED",
            "required_permission": exc.required_permission,
            "path": exc.path,
            "raw_message": exc.message,
        },
    )


@app.exception_handler(ContainerNotFoundError)
def container_not_found_error_handler(
    _request: Request,
    exc: ContainerNotFoundError,
):
    return JSONResponse(
        status_code=404,
        content={
            "detail": str(exc),
            "error_code": "CONTAINER_NOT_FOUND",
        },
    )


@app.exception_handler(ProxmoxConnectionError)
def proxmox_connection_error_handler(
    _request: Request,
    exc: ProxmoxConnectionError,
):
    logger.error("Proxmox connection error: %s", exc.message)
    return JSONResponse(
        status_code=503,
        content={
            "detail": exc.message or "Falha na comunicação com o Proxmox VE.",
            "error_code": "PROXMOX_CONNECTION_ERROR",
        },
    )


@app.exception_handler(ProxmoxAPIError)
def proxmox_api_error_handler(
    _request: Request,
    exc: ProxmoxAPIError,
):
    status_code = exc.status_code if exc.status_code and 400 <= exc.status_code < 600 else 502
    logger.error("Proxmox API error [%s]: %s", status_code, exc.message)
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": f"Erro na API do Proxmox VE: {exc.message}",
            "error_code": "PROXMOX_API_ERROR",
            "raw_message": exc.message,
        },
    )


api_router = APIRouter(prefix="/api")

api_router.include_router(
    tags=["users"],
    router=users
)

api_router.include_router(
    tags=["auth"],
    router=auth
)

api_router.include_router(
    tags=["containers"],
    router=containers
)

api_router.include_router(
    tags=["templates"],
    router=templates
)

api_router.include_router(
    tags=["jobs"],
    router=jobs
)

api_router.include_router(
    tags=["health"],
    router=health
)

api_router.include_router(
    tags=["monitoring"],
    router=monitoring
)

api_router.include_router(
    tags=["access_tokens"],
    prefix="/access-token",
    router=access_tokens
)

api_router.include_router(
    tags=["components"],
    router=components
)

api_router.include_router(
    tags=["cloud"],
    router=cloud_router
)

api_router.include_router(
    agent_router
)

# Incluir o roteador API na aplicação principal
app.include_router(api_router)

# Roteadores de WebSocket permanecem sem o prefixo /api, pois o frontend os consome assim
app.include_router(
    websocket
)

app.include_router(
    console_router
)

# ============================================================
# Single Server Deployment - Serve Static Frontend
# ============================================================

app.mount("/assets", StaticFiles(directory="static/assets", check_dir=False), name="assets")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
        
    static_file_path = os.path.join("static", full_path)
    if os.path.isfile(static_file_path):
        return FileResponse(static_file_path)
        
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
        
    raise HTTPException(status_code=404, detail="Not Found")

