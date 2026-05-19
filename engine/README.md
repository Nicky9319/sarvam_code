# Ticket Classification Pipeline — Engine

Production-grade pipeline for classifying enterprise support tickets using Sarvam's LLM API.

## Architecture

Built on the class-generator layered pattern. Layers (bottom-up):

```
Models          → DomainState + Pydantic data models
Reducers        → BaseReducers subclass, all state mutations
Application     → Business logic (adaptive batching, partial failures)
Operators       → HTTPAPIClient, DBDatabase, APIRoutesHandler (runtime state)
Orchestrator    → Wires all layers, public API
```

**Key design decisions:**
- **Stateless**: request-response only, no StateStore persistence needed
- **No Event Bus** (for now): internal events can be added later via BaseEventBus
- **No Control Loop**: no APScheduler — single request cycle only
- **No worker loops**: all processing is synchronous within a single request

## File Structure

```
engine/
├── __init__.py
├── orchestrator.py               # TicketPipeline — wires all layers
├── reducers.py                   # TicketPipelineReducers — state mutations only
├── application.py               # TicketPipelineApplication — business logic
├── models/
│   ├── __init__.py
│   └── models.py                # DomainState + sub-models (TicketModel,
│                               # ClassificationResult, BatchConfigModel,
│                               # ProcessingStatsModel, Sarvam_APIError)
└── operators/
    ├── __init__.py
    ├── operators.py             # TicketPipelineOperators — runtime state owner
    ├── api_routes_handler.py    # FastAPI + SlowAPI HTTP server (/api/v1/tickets/*)
    ├── http_client.py           # HTTPAPIClient — Sarvam API calls with retry
    └── DB/
        └── db.py                # DBDatabase — MySQL connection pool (stub)
```

## Layers

### Models (`models/models.py`)

Pure Pydantic data models. No logic, no runtime objects.

| Model | Purpose |
|---|---|
| `TicketModel` | Incoming support ticket |
| `ClassificationResult` | Per-ticket classification output |
| `BatchConfigModel` | Batching parameters |
| `ProcessingStatsModel` | Counters (received, classified, failed, batches) |
| `DomainState` | Single source of truth — holds all above as fields |
| `Sarvam_APIError` | Error sentinel for API failures |

### Reducers (`reducers.py`)

The only layer that writes to `DomainState`. Inherits from `BaseReducers` which provides:
- `_pre_hook` — type-hint-driven validation before every public async method
- `_post_hook` — automatic DB sync via `PatchManager` + `StateStoreSidecar` (skipped if sidecar is `None`)
- `call_depth_var` — prevents nested reducer calls from triggering multiple DB writes

**Key rule:** Do not prefix reducer methods with `_` — the wrapper only applies to public async methods.

### Application (`application.py`)

Business logic layer. Defines the public API contract and orchestrates reducers and operators. Handles adaptive batching, partial failure handling, and immediate estimate computation.

### Operators (`operators/`)

Owns all runtime infrastructure — objects that cannot be serialised:

| Component | File | Responsibility |
|---|---|---|
| `HTTPAPIClient` | `http_client.py` | All external HTTP calls to Sarvam API. Retry with exponential backoff + jitter. |
| `DBDatabase` | `DB/db.py` | MySQL connection pool via aiomysql. Currently a stub; ready for persistence. |
| `APIRoutesHandler` | `api_routes_handler.py` | FastAPI + SlowAPI HTTP server on port 8000. |

### Orchestrator (`orchestrator.py`)

Constructs all layers in dependency order and mirrors Application Layer methods as its own public API. No business logic.

Dependency order:
```
Logger → Reducers → Operators → Application
```

## Usage

```python
from engine import TicketPipeline, TicketModel

pipeline = TicketPipeline(sarvam_api_key="your-key")
await pipeline.initialize()

tickets = [
    TicketModel(ticket_id="T001", subject="Printer broken", description="..."),
    TicketModel(ticket_id="T002", subject="App crash", description="..."),
]

response = await pipeline.process_tickets(tickets)
print(f"Success: {response.success_count}, Failed: {response.failure_count}")
```

## Immediate Estimate

```python
estimate = await pipeline.process_tickets(tickets, estimate_only=True)
print(estimate.estimated_batches)   # How many batches
print(estimate.estimated_tokens)    # Total token budget needed
```

## Base Classes Used

| Base Class | Location | Used For |
|-----------|----------|----------|
| `BaseReducers` | `classes.BaseReducers` | Validation wrapping, `_pre_hook`, `_post_hook` |
| `Logger` | `classes.Logger` | Hierarchical async logging |
| `HTTPAPIClient` | `engine/operators/http_client.py` | Sarvam API calls with retry |

## What Was Excluded (not needed for stateless pipeline)

- **Event Bus** — no internal pub/sub events yet; can be added via `BaseEventBus`
- **Control Loop** — no APScheduler (no continuous reconciliation)
- **StateStore persistence** — all state is per-request only; `StateStoreSidecar` is a no-op stub
- **Worker loops** — no background asyncio tasks