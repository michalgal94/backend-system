from uuid import UUID

from .models import AuditRecord


class InMemoryAuditRepository:
    """An upsert-style repository; replace it with durable storage in production."""

    def __init__(self) -> None:
        self._records: dict[UUID, AuditRecord] = {}

    def upsert(self, record: AuditRecord) -> AuditRecord:
        self._records[record.job_id] = record
        return record

    def get(self, job_id: UUID) -> AuditRecord | None:
        return self._records.get(job_id)
