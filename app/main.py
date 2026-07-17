# Depois eu vejo se precisa disso.
# from app.api.audit_logs import router as audit
# from app.api.container_actions import router as actions


from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse

from app.api.users import router as users
from app.api.auth import router as auth
from app.api.containers import router as containers
from app.api.jobs import router as jobs
from app.api.templates import router as templates
from app.api.health import router as health
from app.api.monitoring import router as monitoring
from app.api.websocket import router as websocket
from app.api.access_tokens import router as access_tokens
from app.console.websocket_console import router as console_router
from app.core.exceptions import AuthenticationError, DomainValidationError
from app.services.monitoring.tasks.adapter import metrics_collector
from app.services.job_events import job_event_manager
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_event_manager.loop = asyncio.get_running_loop()
    print(f"[Lifespan DEBUG] Registrou o event loop principal no job_event_manager: {job_event_manager.loop}")
    task = asyncio.create_task(metrics_collector.start())
    yield
    await metrics_collector.stop()
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


app.include_router(
    tags=["users"],
    router=users
)

app.include_router(
    tags=["auth"],
    router=auth
)

app.include_router(
    tags=["containers"],
    router=containers
)

app.include_router(
    tags=["templates"],
    router=templates
)

app.include_router(
    tags=["jobs"],
    router=jobs
)

# app.include_router(
#     actions
# )

# app.include_router(
#     audit
# )

app.include_router(
    tags=["health"],
    router=health
)

app.include_router(
    tags=["monitoring"],
    router=monitoring
)

app.include_router(
    tags=["access_tokens"],
    prefix="/access-token",
    router=access_tokens
)

app.include_router(
    websocket
)

app.include_router(
    console_router
)

