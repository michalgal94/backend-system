import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4

import websockets
from fastapi import BackgroundTasks, FastAPI, status
from pydantic import BaseModel, Field

from .analyzer import analyze_document

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("processor-service")
JOB_EVENTS_WS_URL = os.getenv("JOB_EVENTS_WS_URL", "ws://localhost:8000/ws/events")
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "10"))
MAX_CONCURRENT_DOCUMENTS = int(os.getenv("MAX_CONCURRENT_DOCUMENTS", "32"))


class DocumentInput(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    text: str = Field(max_length=1_000_000)


class ProcessRequest(BaseModel):
    job_id: UUID
    documents: list[DocumentInput] = Field(min_length=1, max_length=1000)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.job_slots = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
    app.state.document_slots = asyncio.Semaphore(MAX_CONCURRENT_DOCUMENTS)
    yield


app = FastAPI(title="Processor Service", version="1.0.0", lifespan=lifespan)


async def send_event(event_type: str, job_id: UUID, payload: dict | None = None) -> None:
    event = {"event_id": str(uuid4()), "type": event_type, "job_id": str(job_id), "occurred_at": datetime.now(timezone.utc).isoformat(), "payload": payload}
    for attempt in range(3):
        try:
            async with websockets.connect(JOB_EVENTS_WS_URL, open_timeout=10) as socket:
                await socket.send(__import__("json").dumps(event))
                return
        except Exception as error:
            logger.warning("event delivery attempt %s failed: %s", attempt + 1, error)
            await asyncio.sleep(0.2 * (2**attempt))
    logger.error("event lost after retries: %s", event_type)


async def analyze_one(document: DocumentInput) -> dict:
    async with app.state.document_slots:
        return await asyncio.to_thread(analyze_document, document.id, document.text)


async def process_job(request: ProcessRequest) -> None:
    async with app.state.job_slots:
        try:
            await send_event("job.started", request.job_id)
            results: list[dict | None] = [None] * len(request.documents)
            cursor = 0
            cursor_lock = asyncio.Lock()

            async def worker() -> None:
                nonlocal cursor
                while True:
                    async with cursor_lock:
                        if cursor >= len(request.documents):
                            return
                        index = cursor
                        cursor += 1
                    results[index] = await analyze_one(request.documents[index])

            await asyncio.gather(*(worker() for _ in range(min(8, len(request.documents)))))
            await send_event("job.completed", request.job_id, {"results": results})
        except Exception as error:
            logger.exception("job processing failed: %s", request.job_id)
            await send_event("job.failed", request.job_id, {"error": str(error)})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/process", status_code=status.HTTP_202_ACCEPTED)
async def process(request: ProcessRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    background_tasks.add_task(process_job, request)
    return {"job_id": str(request.job_id), "status": "Accepted"}
