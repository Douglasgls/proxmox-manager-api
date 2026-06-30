from app.repositories.base_repository import BaseRepository

from app.models.job import Job


class JobRepository(
    BaseRepository[Job]
):

    def __init__(
        self,
        db
    ):
        super().__init__(
            db,
            Job
        )


    def get_running(self):

        return (
            self.db
            .query(Job)
            .filter(
                Job.status == "running"
            )
            .all()
        )


    def get_pending(self):

        return (
            self.db
            .query(Job)
            .filter(
                Job.status == "pending"
            )
            .all()
        )
