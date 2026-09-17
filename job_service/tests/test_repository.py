from uuid import uuid4

import pytest
from pydantic import ValidationError

from job_service.app.models import DocumentInput, Job, JobStatus, UpdateJobMetadataRequest
from job_service.app.repository import InMemoryJobRepository


def test_processing_events_transition_job_and_store_results() -> None:
    repository = InMemoryJobRepository()
    job = repository.create(Job(documents=[DocumentInput(id="doc-1", text="text")]))

    assert repository.apply_event("job.started", job.id, None).status is JobStatus.PROCESSING
    completed = repository.apply_event("job.completed", job.id, {"results": [{"document_id": "doc-1"}]})
    assert completed.status is JobStatus.COMPLETED
    assert completed.results == [{"document_id": "doc-1"}]


def test_unknown_event_and_job_are_ignored() -> None:
    repository = InMemoryJobRepository()
    assert repository.apply_event("job.unknown", uuid4(), None) is None


def test_terminal_job_is_not_reverted_by_late_events() -> None:
    repository = InMemoryJobRepository()
    job = repository.create(Job(documents=[DocumentInput(id="doc-1", text="text")]))

    assert repository.apply_event("job.completed", job.id, {"results": []}).status is JobStatus.COMPLETED
    assert repository.apply_event("job.started", job.id, None) is None
    assert repository.apply_event("job.failed", job.id, {"error": "late failure"}) is None
    assert repository.get(job.id).status is JobStatus.COMPLETED


def test_client_metadata_can_be_updated_without_changing_status() -> None:
    repository = InMemoryJobRepository()
    job = repository.create(Job(documents=[DocumentInput(id="doc-1", text="text")]))

    updated = repository.update(job.id, **UpdateJobMetadataRequest(title="Contract", tags=["legal"]).model_dump(exclude_unset=True))

    assert updated.title == "Contract"
    assert updated.tags == ["legal"]
    assert updated.status is JobStatus.PENDING


def test_metadata_request_rejects_processing_fields() -> None:
    with pytest.raises(ValidationError):
        UpdateJobMetadataRequest.model_validate({"status": "Completed"})
