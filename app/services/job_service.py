from datetime import datetime
import logging

from app.models.job import Job

from app.repositories.job_repository import (
    JobRepository
)
from app.services.job_events import job_event_manager


logger = logging.getLogger(__name__)


class JobService:

    def __init__(
        self,
        repository: JobRepository
    ):
        self.repository = repository


    def create(
        self,
        job_type,
        target=None
    ):

        job = Job(
            type=job_type,
            status="PENDING",
            target_container=target,
            current_step="Request received",
        )

        created_job = (
            self.repository
            .create(job)
        )

        self._publish(
            created_job,
            "job_created",
        )

        return created_job

    def list(self):

        return (
            self.repository
            .list()
        )


    def get(
        self,
        job_id
    ):

        job = (
            self.repository
            .get(
                job_id
            )
        )

        if not job:
            raise ValueError(
                "Job não encontrado"
            )

        return job


    def start(
        self,
        job_id
    ):

        job = (
            self.repository
            .get(
                job_id
            )
        )

        job.status = "RUNNING"
        job.progress = 10
        job.started_at = datetime.now()
        job.current_step = "Creating container"

        updated_job = (
            self.repository
            .update(job)
        )

        self._publish(
            updated_job,
            "job_started",
        )

        return updated_job


    def update_progress(
        self,
        job_id,
        progress: int,
        current_step: str | None = None,
        current_component: str | None = None,
        event: str = "job_updated",
        container_id: int | None = None,
        target_container: str | None = None,
        output: str | None = None,
        error: str | None = None,
    ):

        job = self.get(
            job_id
        )
        job.progress = progress

        if current_step is not None:
            job.current_step = current_step

        if current_component is not None:
            job.current_component = current_component

        if container_id is not None:
            job.container_id = container_id

        if target_container is not None:
            job.target_container = target_container

        if output is not None:
            if job.output:
                job.output += f"\n{output}"
            else:
                job.output = output

        if error is not None:
            job.error = error

        updated_job = (
            self.repository
            .update(job)
        )

        self._publish(
            updated_job,
            event,
        )

        return updated_job


    def finish(
        self,
        job_id,
        output=None
    ):

        job = (
            self.repository
            .get(
                job_id
            )
        )

        job.status = "COMPLETED"
        job.progress = 100
        job.current_step = "Finished"
        job.current_component = None

        job.output = (
            output
        )
        job.finished_at = datetime.now()

        updated_job = (
            self.repository
            .update(job)
        )

        self._publish(
            updated_job,
            "job_finished",
        )

        return updated_job


    def fail(
        self,
        job_id,
        error,
    ):

        job = self.get(
            job_id
        )
        job.status = "FAILED"
        job.error = str(error)
        job.current_step = "Failed"
        job.finished_at = datetime.now()

        updated_job = (
            self.repository
            .update(job)
        )

        self._publish(
            updated_job,
            "job_failed",
        )

        return updated_job

    def _publish(
        self,
        job: Job,
        event: str,
    ):
        payload = self._build_event_payload(
            job=job,
            event=event,
        )

        logger.info(
            "Job %s: %s (%s%%) %s",
            job.id,
            job.status,
            job.progress,
            job.current_step,
        )

        job_event_manager.publish(
            job.id,
            payload,
        )
    def build_event_payload(
        self,
        job: Job,
        event: str,
    ) -> dict:

        return {
            "event": event,
            "job_id": job.id,
            "type": job.type,
            "status": job.status,
            "progress": job.progress,
            "current_step": job.current_step,
            "current_component": job.current_component,
            "container_id": job.container_id,
            "target_container": job.target_container,
            "output": job.output,
            "error": job.error,
            "started_at": (
                job.started_at.isoformat()
                if job.started_at
                else None
            ),
            "finished_at": (
                job.finished_at.isoformat()
                if job.finished_at
                else None
            ),
            "created_at": (
                job.created_at.isoformat()
                if job.created_at
                else None
            ),
        }

    def _build_event_payload(
        self,
        job: Job,
        event: str,
    ) -> dict:

        return self.build_event_payload(
            job=job,
            event=event,
        )
