import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.staticfiles import StaticFiles

from .models import AuditSummary, CreateJobRequest, Job, JobStatus, ProcessingEvent, UpdateJobMetadataRequest
from .repository import InMemoryJobRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("job-service")
PROCESSOR_URL = os.getenv("PROCESSOR_URL", "http://localhost:8001")
AUDIT_URL = os.getenv("AUDIT_URL", "http://localhost:8002")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.repository = InMemoryJobRepository()
    app.state.event_ids: set[UUID] = set()
    app.state.event_lock = asyncio.Lock()
    yield


app = FastAPI(title="Job Service", version="1.0.0", lifespan=lifespan)
app.mount("/ui", StaticFiles(directory=Path(__file__).parent.parent / "ui", html=True), name="ui")


async def report_audit(job: Job) -> None:
    # Audit is a best-effort integration and never changes the processing outcome
    if job.status not in {JobStatus.COMPLETED, JobStatus.FAILED}:
        return
    summary = AuditSummary(
        job_id=job.id,
        status=job.status,
        title=job.title,
        tags=job.tags,
        document_count=len(job.documents),
        error=job.error,
    )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
            response = await client.post(f"{AUDIT_URL}/api/audit", json=summary.model_dump(mode="json"))
            response.raise_for_status()
    except httpx.HTTPError as error:
        logger.warning("audit submission failed for %s: %s", job.id, error)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/jobs", response_model=list[Job])
async def list_jobs() -> list[Job]:
    return app.state.repository.list()


@app.get("/api/jobs/{job_id}", response_model=Job)
async def get_job(job_id: UUID) -> Job:
    job = app.state.repository.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.patch("/api/jobs/{job_id}", response_model=Job)
async def update_job_metadata(job_id: UUID, request: UpdateJobMetadataRequest) -> Job:
    changes = request.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="At least one metadata field is required")
    job = app.state.repository.update(job_id, **changes)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.delete("/api/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: UUID) -> None:
    if not app.state.repository.delete(job_id):
        raise HTTPException(status_code=404, detail="Job not found")


@app.post("/api/jobs", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
async def create_job(request: CreateJobRequest) -> Job:
    job = app.state.repository.create(
        Job(documents=request.documents, title=request.title, tags=request.tags)
    )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
            response = await client.post(f"{PROCESSOR_URL}/api/process", json={"job_id": str(job.id), "documents": [d.model_dump() for d in job.documents]})
            response.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as error:
        logger.warning("processor submission failed for %s: %s", job.id, error)
        failed_job = app.state.repository.update(job.id, status=JobStatus.FAILED, error=f"Could not submit to processor: {error}")
        if failed_job is not None:
            asyncio.create_task(report_audit(failed_job))
        raise HTTPException(
            status_code=503,
            detail={"message": "Processor Service is unavailable", "job_id": str(job.id)},
        ) from error
    return job


@app.websocket("/ws/events")
async def receive_events(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            event = ProcessingEvent.model_validate_json(await websocket.receive_text())
            # Serialize event de-duplication because multiple Processor connections may arrive together
            async with app.state.event_lock:
                if event.event_id in app.state.event_ids:
                    continue
                app.state.event_ids.add(event.event_id)
                job = app.state.repository.apply_event(event.type, event.job_id, event.payload)
            if job is None:
                logger.warning("ignored unknown event or job: %s", event.model_dump_json())
            else:
                asyncio.create_task(report_audit(job))
    except WebSocketDisconnect:
        logger.info("processor websocket disconnected")
    except Exception as error:
        logger.warning("invalid event: %s", error)
        await websocket.close(code=1003)
