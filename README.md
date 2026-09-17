# Real-Time Document Processing System

A Python 3.13 backend home-assignment solution composed of two required services and one optional bonus service. It demonstrates REST service-to-service calls, WebSocket lifecycle events, bounded concurrent document processing, validation, failure handling, tests and clear trade-offs.

# What It Does

The client creates and queries document-processing jobs through Job Service, which sends work to Processor Service over REST.
Processor Service analyzes documents asynchronously and sends lifecycle events back over WebSocket. After a job reaches a terminal state, Job Service sends a compact summary to the Audit Service over REST.

Each document result includes word count, unique word count, five most frequent words, SHA-256 digest, and character count.

# Architecture

```text
Client -- REST /api/jobs --> Job Service -- REST /api/process --> Processor Service
                                  ^                                  |
                                  |------ WebSocket /ws/events -------|
                                  |
                                  |------ REST /api/audit -----------> Audit Service
```

| Service | Port | Responsibility |
| --- | --- | --- |
| Job Service | 8000 | Public job API, job lifecycle/state, WebSocket event receiver |
| Processor Service | 8001 | Concurrent document analysis and lifecycle event producer |
| Audit Service | 8002 | Terminal-job audit summaries |

The lifecycle is `Pending -> Processing -> Completed` or `Pending/Processing -> Failed`. Job Service is the source of truth for lifecycle status. A client can update descriptive metadata only (`title`, `tags`). it cannot change processing status or results.

Repository structure:

- `job_service/`
  - `app/models.py`
    - Job, document, lifecycle, event, and audit-summary models
  - `app/repository.py`
    - In-memory job storage and lifecycle transitions
  - `app/main.py`
    - FastAPI composition, public REST API, WebSocket event receiver,
      and REST clients for Processor and Audit services
  - `tests/`
    - Job lifecycle, metadata, and state-protection tests

- `processor_service/`
  - `app/analyzer.py`
    - Word statistics, top words, SHA-256, and document metadata
  - `app/main.py`
    - Internal processing API, bounded concurrency, and WebSocket event delivery
  - `tests/`
    - Document-analysis tests

- `audit_service/`
  - `app/models.py`
    - Terminal-job audit summary contract
  - `app/repository.py`
    - In-memory idempotent audit upsert
  - `app/main.py`
    - Audit REST API
  - `tests/`
    - Audit upsert tests

- `docker-compose.yml`
  - Local orchestration and service-to-service environment configuration

- `requirements-dev.txt`
  - Development and test dependencies

The structure is intentionally lightweight for the assignment time-box. Models, repositories, API composition, processing logic, and tests are separated without introducing layers that don't provide clear value for this small system.

# Requirements

- Python 3.11 or later; developed and verified with Python 3.13
- Docker Desktop is optional, only for Docker Compose execution

# Setup

From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```
There is no separate compilation/build phase for this Python service. Dependency installation plus the automated test suite is the build verification step.

# Run Locally

Open three PowerShell terminals in the repository root. Activate the virtual environment in each terminal:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then run one command in each terminal:

```powershell
py -m uvicorn job_service.app.main:app --port 8000
py -m uvicorn processor_service.app.main:app --port 8001
py -m uvicorn audit_service.app.main:app --port 8002
```

Health endpoints:

```text
http://localhost:8000/health
http://localhost:8001/health
http://localhost:8002/health
```

# Run With Docker Compose

```powershell
docker compose up --build
```
Docker Compose sets service-discovery URLs automatically. Stop containers with `docker compose down`.

# Swagger UI

FastAPI provides an interactive Swagger UI for each service:

- Job Service: `http://localhost:8000/docs`
- Processor Service: `http://localhost:8001/docs`
- Audit Service: `http://localhost:8002/docs`

The normal user flow begins in Job Service Swagger with `POST /api/jobs`. `POST /api/process` and `POST /api/audit` are internal service-to-service endpoints and documented for inspection and testing.

# End-to-End Flow

```powershell
$job = Invoke-RestMethod -Method Post http://localhost:8000/api/jobs -ContentType application/json -Body '{"title":"Demo","tags":["sample"],"documents":[{"id":"doc-1","text":"Hello hello world, document world."}]}'
Start-Sleep -Seconds 5
Invoke-RestMethod "http://localhost:8000/api/jobs/$($job.id)" | ConvertTo-Json -Depth 8
Invoke-RestMethod "http://localhost:8002/api/audit/$($job.id)" | ConvertTo-Json -Depth 8
```

The first response is `202 Accepted`. Poll the job endpoint until its `Completed` or `Failed`. completion is asynchronous by design.
The final object is `Completed` and has word count, unique count, five frequent words, SHA-256 and character count for every document.

# API Summary

1. Job Service

| Method | Endpoint | Behaviour |
| --- | --- | --- |
| `POST` | `/api/jobs` | Creates a job and submits it to Processor Service; returns `202` |
| `GET` | `/api/jobs` | Lists in-memory jobs |
| `GET` | `/api/jobs/{jobId}` | Returns a job or `404` |
| `PATCH` | `/api/jobs/{jobId}` | Updates client-owned `title` and/or `tags` only |
| `DELETE` | `/api/jobs/{jobId}` | Deletes an in-memory job
 returns `204` or `404` |
| `GET` | `/health` | Health check |
| WebSocket | `/ws/events` | Receives Processor lifecycle events |

2. Processor Service

| Method | Endpoint | Behaviour |
| --- | --- | --- |
| `POST` | `/api/process` | Internal work-acceptance endpoint
 returns `202` |
| `GET` | `/health` | Health check |

3. Audit Service

| Method | Endpoint | Behaviour |
| --- | --- | --- |
| `POST` | `/api/audit` | Internal, idempotent upsert of a terminal-job summary |
| `GET` | `/api/audit/{jobId}` | Returns an audit record or `404` |
| `GET` | `/health` | Health check |

# Event Contract

Processor Service sends JSON events to Job Service over WebSocket:

```json
{
  "event_id": "UUID",
  "type": "job.started | job.completed | job.failed",
  "job_id": "UUID",
  "occurred_at": "ISO-8601 UTC timestamp",
  "payload": { "results": [], "error": "optional failure message" }
}
```

Events have UUIDs and are idempotently consumed. Job Service ignores duplicate events and those that would regress a terminal job state.

# Technical Decisions

1. Technology: Python, FastAPI and Async I/O

Since this is an API-oriented system operating in an environment that also involves AI, I used Python with FastAPI. It provides asynchronous support, typed request validation, OpenAPI/Swagger documentation, REST routes, and boasts a very strong ecosystem for the AI ​​domain. `httpx` is used for asynchronous REST calls and `websockets` for the Processor-to-Job event connection.

Benefits:

- concise and readable implementation
- automatic request validation and interactive API documentation
- `asyncio` support without blocking HTTP request handling

Trade-offs:

- CPU-heavy work is not made parallel merely by async code
- dependency versions require active management and security scanning

2. Service Boundaries

Job Service owns the public API and the authoritative job lifecycle, Processor Service owns document analysis, and Audit Service is an  independent terminal-summary consumer. Job Service calls Processor Service by REST because it needs a clear request/accepted response. Processor returns lifecycle changes asynchronously by WebSocket because processing may outlive the HTTP request.

Benefits:

- ownership is explicit and each service has a narrow responsibility
- Processor can scale independently from the public API
- an asynchronous event channel makes the lifecycle visible without client-held work requests

Trade-offs:

- network failures and eventual consistency must be handled
- operating multiple services is more complex than a monolith

3. REST and WebSocket Contracts

`POST /api/jobs` creates and submits a job. `POST /api/process` accepts it with `202 Accepted`. Processor sends `job.started`, `job.completed`, and `job.failed` events containing an `event_id`, `job_id`, timestamp and optional results/error payload. The contract is intentionally small and versionable.

Benefits:

- REST provides a clear request-and-accept contract between Job Service and Processor Service
- WebSocket events allow processing to complete asynchronously without keeping the original HTTP request open
- `event_id` is retained in memory by Job Service and duplicate events are ignored 

Trade-offs:

- Network failures, late events and duplicate events require explicit handling
- WebSocket delivery adds connection-management complexity compared with a synchronous-only flow

4. Lifecycle and CRUD Scope

The lifecycle is `Pending -> Processing -> Completed` or `Failed`. Job Service owns state changes from Processor events. CRUD is deliberately constrained: clients can create, list, retrieve, delete, and patch only descriptive fields (`title`, `tags`). 

Benefits:

- Job lifecycle ownership remains in Job Service and Processor events
- Clients cannot overwrite processing status, results or failure information. this prevents them from bypassing processing or corrupting system-owned data
- Restricting PATCH to `title` and `tags` preserves lifecycle integrity

Trade-offs:

- Jobs cannot be edited after submission
- Cancellation is not supported
- Future document editing or cancellation would require explicit lifecycle rules and endpoints

5. Concurrency Strategy

Processor uses three limits: 10 concurrent jobs, 8 workers per job, and 32 documents globally. Workers claim document indexes incrementally rather than creating a task for every document. Analysis runs in `asyncio.to_thread` so hashing/text analysis doesnt block the event loop.

Benefits:

- meets the required ten-job scenario
- prevents unbounded memory, queue, and thread pressure for up to 1,000 documents per job
- preserves result order by storing each result at its source index

Trade-offs:

- a job can wait behind other jobs for one of the 32 shared document slots;
- threads are appropriate for the assignment's small operations, but CPU-intensive workloads would need worker processes or a dedicated execution tier.

6. In-Memory Storage Behind Repositories

Job and Audit data are held in small in-memory repository classes. This keeps setup trivial and lets endpoint code depend on a repository boundary rather than a database implementation.

Benefits:

- no external infrastructure is needed
- fast, deterministic setup for the assignment
- a Postgres/SQLAlchemy repository can replace the implementation without changing route contracts
- ideal for demonstrating the architecture in an assignment

Trade-offs:

- data and idempotency keys lost after restart
- cannot coordinate state across instances
- no durability guarantees for events

7. Failure Handling and Delivery Semantics

Job Service has a three-second Processor REST timeout. On submission failure it records `Failed` and returns `503` with the generated job ID. Processor retries each WebSocket event three times with exponential backoff. Job Service logs, rather than crashes on, malformed/unknown events and duplicate events.

Benefits:

- Timeouts prevent unavailable dependencies from blocking requests indefinitely
- Retry and idempotency handling make duplicate event delivery safe
- Processor and Audit failures are isolated from the primary job API where appropriate

Trade-offs:

- Event delivery is best-effort rather than guaranteed
- WebSocket disconnects, restarts and exhausted retries can result in lost events

8. Logging and Observability

All services emit timestamped logging. Job Service logs processor and audit submission failures. Processor Service logs processing exceptions and event-delivery retries. Health endpoints provide basic liveness checks.

Benefits:

- Timestamped logs make processing and delivery failures easier to investigate
- Health endpoints provide a simple liveness signal for each service
- Logging focuses on meaningful failure paths within the assignment scope

Trade-offs:

- There are no correlation IDs across REST and WebSocket calls
- Metrics, tracing, dashboards, and centralized log retention are not implemented
- Logs alone are insufficient for larger-scale monitoring.

9. Testing Strategy

```powershell
py -m pytest job_service/tests processor_service/tests audit_service/tests -q
```

The automated unit tests cover document analysis, edge cases, lifecycle state transitions, metadata restrictions, terminal-state protection and audit upsert idempotency.

The PowerShell flow above is a manual end-to-end REST/WebSocket/Audit proof.

Benefits:

- Unit tests cover the highest-risk business rules and deterministic document analysis.
- Tests are fast to run and require no external infrastructure.

Trade-offs:

- Full REST/WebSocket integration tests are not yet implemented.
- Retry, timeout, and service-outage behavior would benefit from fault-injection tests.

10. Scope and Explicit Omissions

The solution intentionally omits authentication/authorization, external databases, message brokers, Redis, Kubernetes/cloud deployment, WebSocket clustering, CI/CD, cancellation, and result pagination. These omissions follow the assignment time-box, and are documented rather than hidden.

The Audit Service was added only after the required Job/Processor workflow, tests and documentation were completed.

Benefits:

- The implementation remains focused on the mandatory requirements and the assignment time-box.
- Avoiding unnecessary infrastructure keeps the solution easy to run, review, and explain.
- The optional Audit Service was added only after the mandatory workflow was complete.

Trade-offs:

- Authentication, authorization, persistent storage, durable messaging, and deployment concerns are not implemented.
- The system is intentionally not suitable for multi-instance or large-scale deployment as-is.
- Some operational capabilities are documented in the improvement section rather than implemented.

# Concurrency and Performance

The assignment target is at least 10 concurrent jobs with up to 1,000 documents each. Processor Service uses bounded asynchronous work:

- a job semaphore allows at most 10 active jobs
- each active job starts at most 8 document workers
- a shared semaphore allows at most 32 document analyses globally
- CPU-oriented analysis is run with `asyncio.to_thread`, keeping the async event loop responsive

This avoids creating an unbounded number of tasks for 10,000 documents. The trade-off is that a job may wait for a global document slot under heavy load, in return for stable resource use.

# Reliability and Edge Cases

- Invalid input: FastAPI/Pydantic validates request bodies, document bounds (1-1,000), field types, and metadata constraints; invalid requests return `422`
- Processor unavailable: Job Service uses a three-second REST timeout, records the job as `Failed`, and returns `503` with the newly created `job_id`
- Processor failure: Processor emits `job.failed`; Job Service stores its error
- Duplicate events: Job Service de-duplicates `event_id` in memory
- WebSocket disconnect: Processor attempts delivery three times with exponential backoff. A failed delivery is logged, not guaranteed  after restart/outage
- Audit unavailable: Audit calls have a two-second timeout and are best-effort. An audit failure is logged but cant change a terminal job status
- Unknown job/event: ignored and logged rather than causing a service failure

# Known Limitations 

- Job, audit, and idempotency data are stored in memory and are lost on restart
- WebSocket and audit delivery are best-effort and retries are not durable
- Processing runs within one Python service instance. large CPU-heavy workloads need worker processes or a distributed worker tier
- No authentication, authorization, rate limiting, cancellation, pagination, durable broker or multi-instance WebSocket coordination
- Observability is limited to application logs and health endpoints
- The automated tests focus on unit-level behavior rather than full integration and load scenarios

# Production Improvements

- Persistent storage for jobs, document results, audit records, and idempotency keys
- A transactional outbox and a durable message broker such as RabbitMQ, Kafka, or SQS
- Durable retries, dead-letter queues, replay support, and persistent event deduplication
- Rate limiting, payload-size limits, request-flooding protection, and burst protection for job creation
- Shared coordination and rate-limit storage when running multiple service instances
- Container image packaging, deployment configuration, and environment-specific configuration management
- Authentication for mutating endpoints
- Authorization and role-based access control for users who create, inspect, update, or delete jobs
- Structured JSON logging, correlation IDs propagated through REST and WebSocket events, distributed tracing, metrics, dashboards and alerts
- Worker processes or a distributed worker tier for CPU-heavy document analysis
- Frontend UI for user-friendly interaction with the system
- External database for persistent and scalable data storage
- REST/WebSocket integration tests, concurrency tests, load tests, and fault-injection tests

# Audit Service

The Audit Service receives `POST /api/audit` only for completed or failed jobs and exposes `GET /api/audit/{jobId}`. It stores one upserted record per job ID, making duplicate terminal notifications safe.

Audit is intentionally non-critical: Job Service calls it with a two-second timeout and logs errors without changing the main job result. This ensures the optional service cannot make the mandatory workflow less reliable.

# Assignment Deliverables

- Complete source for Job Service, Processor Service and Audit Service
- REST and WebSocket integration
- Docker Compose configuration
- Swagger UI
- Automated tests
- This README document

# AI Usage Disclosure

Tools used: Codex (GPT-5) assisted with reviewing the assignment, drafting and reviewing code, documentation and local test/run commands.

Significant AI-assisted parts included FastAPI service scaffolding, bounded-concurrency design, WebSocket event contract, Audit Service integration, tests, Docker Compose and documentation structure.
All changes were reviewed and tested locally.

Representative prompts:

- "Design a Python two-service REST/WebSocket document processor with bounded concurrency."
- "List sensible failure behavior and home-assignment trade-offs."
- "Draft concise setup, architecture, and decision documentation."

Example of a changed AI suggestion: I proposed an unrestricted `PATCH /api/jobs/{jobId}` endpoint to make the client-facing API a full CRUD surface. It would let a client overwrite processing state. AI advised against it because a client must not be able to change processing status: doing so could bypass the `Pending -> Processing -> Completed/Failed` lifecycle owned by Processor events. I refined the proposal by limiting `PATCH` to client-owned descriptive metadata (`title`, `tags`). `status`, documents, results, and errors remain managed by the service-to-service processing contract.

Additional example: AI suggested creating one asynchronous task per document, because it is simple and maximizes parallelism. I changed this approach because a single job may contain up to 1,000 documents; creating all tasks at once could consume excessive memory and overload the thread pool. Instead, I used up to eight workers per job and a global semaphore of 32 document analyses, which keeps concurrency bounded while still allowing at least ten jobs to progress concurrently.