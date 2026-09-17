from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, status

from .models import AuditRecord
from .repository import InMemoryAuditRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.repository = InMemoryAuditRepository()
    yield


app = FastAPI(title="Audit Service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/audit", response_model=AuditRecord, status_code=status.HTTP_201_CREATED)
async def create_or_update_audit(record: AuditRecord) -> AuditRecord:
    return app.state.repository.upsert(record)


@app.get("/api/audit/{job_id}", response_model=AuditRecord)
async def get_audit(job_id: UUID) -> AuditRecord:
    record = app.state.repository.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Audit record not found")
    return record
