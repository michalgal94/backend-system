from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    job_id: UUID
    status: str = Field(pattern="^(Completed|Failed)$")
    title: str | None = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=20)
    document_count: int = Field(ge=0, le=1000)
    error: str | None = None
    reported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
