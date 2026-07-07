from fastapi import APIRouter
from fastapi import Depends
from fastapi import WebSocket
from fastapi import WebSocketDisconnect

from app.core.dependencies import (
    get_job_service,
)
from app.dto.response.job import (
    JobResponseDTO,
)
from app.services.job_service import (
    JobService,
)
from app.services.job_events import job_event_manager


router = APIRouter()


@router.get(
    "/jobs",
    response_model=list[JobResponseDTO],
)
def list_all(
    service: JobService = Depends(
        get_job_service
    ),
):

    return service.list()


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponseDTO,
)
def get(
    job_id: str,
    service: JobService = Depends(
        get_job_service
    ),
):

    return service.get(
        job_id
    )


@router.websocket(
    "/jobs/{job_id}/stream"
)
async def stream(
    websocket: WebSocket,
    job_id: str,
    service: JobService = Depends(
        get_job_service
    ),
):
    await websocket.accept()

    try:
        job = service.get(
            job_id
        )
    except ValueError:
        await websocket.close(
            code=1008
        )
        return

    queue = await job_event_manager.subscribe(
        job_id
    )

    try:
        await websocket.send_json(
            service.build_event_payload(
                job=job,
                event="job_snapshot",
            )
        )

        if job.status in {
            "COMPLETED",
            "FAILED",
        }:
            return

        while True:
            event = await queue.get()
            await websocket.send_json(
                event
            )

            if event.get("status") in {
                "COMPLETED",
                "FAILED",
            }:
                break

    except WebSocketDisconnect:
        pass

    finally:
        job_event_manager.unsubscribe(
            job_id,
            queue,
        )
