from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


Tag = Annotated[str, Field(min_length=1, max_length=50)]


class JobStatus(str, Enum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class DocumentInput(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    text: str = Field(max_length=1_000_000)


class CreateJobRequest(BaseModel):
    documents: list[DocumentInput] = Field(min_length=1, max_length=1000)
    title: str | None = Field(default=None, max_length=200)
    tags: list[Tag] = Field(default_factory=list, max_length=20)


class UpdateJobMetadataRequest(BaseModel):
    """Client-owned metadata only; processing state is managed by Processor events."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    tags: list[Tag] | None = Field(default=None, max_length=20)


class Job(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    status: JobStatus = JobStatus.PENDING
    documents: list[DocumentInput]
    title: str | None = None
    tags: list[Tag] = Field(default_factory=list)
    results: list[dict[str, Any]] | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProcessingEvent(BaseModel):
    event_id: UUID
    type: str
    job_id: UUID
    occurred_at: datetime
    payload: dict[str, Any] | None = None


class AuditSummary(BaseModel):
    job_id: UUID
    status: JobStatus
    title: str | None = None
    tags: list[Tag] = Field(default_factory=list)
    document_count: int
    error: str | None = None
    reported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
