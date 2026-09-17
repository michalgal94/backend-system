from datetime import datetime, timezone
from uuid import UUID

from .models import Job, JobStatus


class InMemoryJobRepository:
    """Replace this small interface with a database-backed repository in production."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, Job] = {}

    def create(self, job: Job) -> Job:
        self._jobs[job.id] = job
        return job

    def get(self, job_id: UUID) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        return list(self._jobs.values())

    def delete(self, job_id: UUID) -> bool:
        return self._jobs.pop(job_id, None) is not None

    def update(self, job_id: UUID, **changes: object) -> Job | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        for key, value in changes.items():
            setattr(job, key, value)
        job.updated_at = datetime.now(timezone.utc)
        return job

    def apply_event(self, event_type: str, job_id: UUID, payload: dict | None) -> Job | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None

        if event_type == "job.started":
            if job.status is not JobStatus.PENDING:
                return None
            return self.update(job_id, status=JobStatus.PROCESSING)
        if event_type == "job.completed":
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                return None
            return self.update(job_id, status=JobStatus.COMPLETED, results=(payload or {}).get("results", []))
        if event_type == "job.failed":
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                return None
            return self.update(job_id, status=JobStatus.FAILED, error=(payload or {}).get("error", "Processor failed"))
        return None
