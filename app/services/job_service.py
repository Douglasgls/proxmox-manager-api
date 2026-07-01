from datetime import datetime

from app.models.job import Job

from app.repositories.job_repository import (
    JobRepository
)


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
            status="pending",
            target_container=target
        )

        return (
            self.repository
            .create(job)
        )


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

        job.status = (
            "running"
        )
        job.progress = 10
        job.started_at = datetime.now()

        return (
            self.repository
            .update(job)
        )


    def update_progress(
        self,
        job_id,
        progress: int,
    ):

        job = self.get(
            job_id
        )
        job.progress = progress

        return (
            self.repository
            .update(job)
        )


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

        job.status = (
            "completed"
        )
        job.progress = 100

        job.output = (
            output
        )
        job.finished_at = datetime.now()

        return (
            self.repository
            .update(job)
        )


    def fail(
        self,
        job_id,
        error,
    ):

        job = self.get(
            job_id
        )
        job.status = "failed"
        job.error = str(error)
        job.finished_at = datetime.now()

        return (
            self.repository
            .update(job)
        )
