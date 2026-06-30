# Depois eu vejo se precisa disso.
# from app.api.audit_logs import router as audit
# from app.api.jobs import router as jobs
# from app.api.container_actions import router as actions


from fastapi import FastAPI

from app.api.users import router as users
from app.api.containers import router as containers
from app.api.health import router as health


app = FastAPI()


app.include_router(
    users
)

app.include_router(
    containers
)

# app.include_router(
#     jobs
# )

# app.include_router(
#     actions
# )

# app.include_router(
#     audit
# )

app.include_router(
    health
)