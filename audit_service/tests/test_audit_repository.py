from uuid import uuid4

from audit_service.app.models import AuditRecord
from audit_service.app.repository import InMemoryAuditRepository


def test_upsert_keeps_one_record_per_job() -> None:
    repository = InMemoryAuditRepository()
    job_id = uuid4()
    repository.upsert(AuditRecord(job_id=job_id, status="Completed", document_count=2))
    updated = repository.upsert(AuditRecord(job_id=job_id, status="Failed", document_count=2, error="late failure"))

    assert repository.get(job_id) == updated
    assert repository.get(job_id).status == "Failed"
