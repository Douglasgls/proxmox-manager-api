# Depois eu vejo se precisa disso.
# from app.api.audit_logs import router as audit
# from app.api.container_actions import router as actions


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
from app.core.exceptions import AuthenticationError, DomainValidationError


app = FastAPI()


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
