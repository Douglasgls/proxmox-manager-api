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

        job.output = (
            output
        )

        return (
            self.repository
            .update(job)
        )