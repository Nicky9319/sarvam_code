# Ticket Classification Pipeline

A stateless request-response pipeline that classifies enterprise support tickets using the Sarvam LLM API. Handles batches of up to 500 tickets with adaptive batching, retry with exponential backoff, and partial failure handling.

---

## Architecture Overview

The pipeline uses a **layered architecture** where each layer has exactly one job. Layers only call downward — a higher layer can call a lower layer, but never the reverse.

```
┌──────────────────────────────────────────────────────────────┐
│  Orchestrator (orchestrator.py)                               │
│  Wires all layers together. No business logic.               │
├──────────────────────────────────────────────────────────────┤
│  Application Layer (application.py)                           │
│  Defines the public API. Orchestrates reducers + operators.  │
├──────────────────────────────────────────────────────────────┤
│  Operators (operators/)                                       │
│  Runtime infrastructure: HTTP client, DB, FastAPI server     │
├──────────────────────────────────────────────────────────────┤
│  Reducers (reducers.py)                                       │
│  The only layer that writes state. Validates + syncs to DB.  │
├──────────────────────────────────────────────────────────────┤
│  Models (models/)                                             │
│  Pydantic data models only. No logic.                         │
└──────────────────────────────────────────────────────────────┘
```

**Key design decisions for this pipeline:**
- **Stateless**: request-response only — each request is independent, no state survives across requests
- **No Event Bus**: components communicate directly through method calls (can be added later via `BaseEventBus`)
- **No Control Loop**: no APScheduler — single request cycle only
- **No worker loops**: synchronous processing within each request
- **No StateStore persistence**: `StateStoreSidecar` is a no-op stub; pipeline runs in-memory

---

## All Files

```
sarvam_code/
├── README.md                     # This file — high-level overview
├── NOTES.md                     # Assumptions, tradeoffs, future improvements
├── .env.local                   # Environment variables template
├── engine/
│   ├── __init__.py              # Public exports (TicketPipeline, TicketModel, etc.)
│   ├── orchestrator.py          # TicketPipeline — wires all layers, public entry point
│   ├── reducers.py              # TicketPipelineReducers — state mutations only
│   ├── application.py           # TicketPipelineApplication — business logic
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py            # DomainState + all Pydantic models
│   └── operators/
│       ├── __init__.py
│       ├── operators.py          # TicketPipelineOperators — runtime infrastructure owner
│       ├── api_routes_handler.py # FastAPI + SlowAPI HTTP server
│       ├── http_client.py       # HTTPAPIClient — Sarvam API calls with retry + backoff
│       └── DB/
│           └── db.py           # DBDatabase — MySQL connection pool (stub)
├── engine/
│   └── classes/
│       └── StateStore/
│           └── state_store.py   # StateStoreSidecar stub (no-op for now)
├── classes/
│   ├── BaseReducers/             # Base class for all reducers
│   │   └── base_reducers.py
│   ├── Logger/                   # Logging infrastructure
│   └── BaseEventBus/            # Event bus base (not used in this pipeline)
└── main.py                      # Entry point
```

---

## Layer-by-Layer Breakdown

### Models (`engine/models/models.py`)

Pure Pydantic data models. No logic, no runtime objects. All state lives in `DomainState`.

| Model | Fields | Purpose |
|---|---|---|
| `TicketModel` | `ticket_id`, `subject`, `description`, `priority` | Incoming support ticket |
| `ClassificationResult` | `ticket_id`, `category`, `summary`, `success`, `error` | Per-ticket classification output |
| `BatchConfigModel` | `max_context_window`, `avg_tokens_per_ticket`, `max_batch_size` | Batching parameters |
| `ProcessingStatsModel` | `total_received`, `total_classified`, `total_failed`, `batches_processed` | Counters |
| `DomainState` | `config`, `stats`, `pending_tickets`, `results` | Single source of truth — holds all above |
| `Sarvam_APIError` | — | Error sentinel for API failures |

---

### Reducers (`engine/reducers.py`)

The **only layer that writes to `DomainState`**. Inherits from `BaseReducers` which provides infrastructure for validation and DB sync.

**What `BaseReducers` adds:**
- `__getattribute__` wrapping — every public async method is auto-wrapped with hooks
- `_pre_hook` — type-hint-driven validation before the method runs (Literal, str, list fields)
- `_post_hook` — automatic state persistence via `PatchManager` + `StateStoreSidecar` (silently skipped if sidecar is `None`)
- `call_depth_var` — prevents nested reducer calls from triggering multiple DB writes

**Key rule:** Do not prefix reducer methods with `_` — the wrapper only applies to public async methods.

```python
class TicketPipelineReducers(BaseReducers):
    async def add_tickets(self, tickets: List[TicketModel]) -> None:
        self.domain_state.pending_tickets.extend(tickets)
```

---

### Application (`engine/application.py`)

Business logic layer. Orchestrates reducers and operators. Defines the public API contract. Currently a stub — holds the logic for:
- Adaptive batching by token budget
- Partial failure handling
- Immediate processing estimate
- Retry coordination

```python
class TicketPipelineApplication:
    async def process_tickets(self, tickets, estimate_only=False) -> ProcessTicketsResponse:
        ...
```

---

### Operators (`engine/operators/`)

Owns all **runtime infrastructure** — objects that cannot be serialised. Three sub-components:

| Component | File | Responsibility |
|---|---|---|
| `HTTPAPIClient` | `http_client.py` | All external HTTP calls to Sarvam API. Retry with exponential backoff + jitter. |
| `DBDatabase` | `DB/db.py` | MySQL connection pool via aiomysql. Currently a stub; ready for persistence. |
| `APIRoutesHandler` | `api_routes_handler.py` | FastAPI + SlowAPI HTTP server on port 8000. |

---

### Orchestrator (`engine/orchestrator.py`)

Constructs all layers in the **correct dependency order** and exposes Application Layer methods as its own public API. No business logic here.

**Dependency order:**
```
Logger → Reducers → Operators → Application
```

**Initialization sequence:**
1. Logger initialized
2. Reducers initialized with `DomainState()`
3. Operators initialized (creates HTTPAPIClient, DBDatabase, APIRoutesHandler)
4. Application created with references to reducers and operators
5. `application` injected directly into `APIRoutesHandler` (avoids circular dependency)
6. FastAPI server started

---

## Base Classes Used

### `BaseReducers` (`classes/BaseReducers/base_reducers.py`)

The foundation for all reducer classes. Every service that needs state management uses this.

**Key mechanisms:**

| Mechanism | What it does |
|---|---|
| `__getattribute__` wrapping | Intercepts every public async method call and wraps it |
| `_pre_hook` | Runs before method — validates inputs based on type hints |
| `_post_hook` | Runs after method — syncs DomainState to DB via PatchManager |
| `call_depth_var` | Thread-local counter; nested calls don't double-write |

### `StateStoreSidecar` (`engine/classes/StateStore/state_store.py`)

A minimal stub. `apply_patch()` is a no-op. Pass `None` to Reducers to run entirely in-memory.

### `Logger` (`classes/Logger/`)

Hierarchical async logging. Used throughout all layers via `LogAgent` instances.

---

## Key Concepts

### Single Writer Rule

Reducers are the **only** layer that writes to `DomainState`. No other layer modifies state directly. This makes every state change traceable and avoids race conditions.

### Stateless Pipeline

Each request is independent. There is no:
- **Event Bus** — components communicate directly through method calls
- **Control Loop** — no APScheduler, no background reconciliation
- **StateStore persistence** — no state survives across requests

**Request flow:** `request → Orchestrator → Application → Reducers → response`

---

## API Routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/tickets/health` | Health check — returns `{"status": "ok"}` |
| `POST` | `/api/v1/tickets/processTickets` | Process a batch of tickets |

---

## Features

| Feature | Implementation |
|---|---|
| Adaptive batching | Splits tickets by token budget (~80% of context window per batch, max 50 tickets) |
| Retry + backoff | Exponential backoff + jitter for rate limits (429) and transient errors (5xx, timeouts) |
| Partial failure | Individual ticket failures in `ClassificationResult`; batch continues regardless |
| Immediate estimate | `estimate_only=True` returns batches/tokens/time before any async work |

---

## Configuration

### Environment Variables (`.env.local`)

| Variable | Default | Description |
|---|---|---|
| `SARVAM_API_KEY` | — | Sarvam API key (required) |
| `SARVAM_BASE_URL` | `https://api.sarvam.ai` | Sarvam API base URL |
| `MYSQL_HOST` | `localhost` | MySQL host |
| `MYSQL_PORT` | `3306` | MySQL port |
| `MYSQL_USER` | `root` | MySQL user |
| `MYSQL_PASSWORD` | — | MySQL password |
| `MYSQL_DATABASE` | `ticket_pipeline` | MySQL database name |
| `API_HOST` | `0.0.0.0` | FastAPI server host |
| `API_PORT` | `8000` | FastAPI server port |
| `LOG_LEVEL` | `INFO` | Logger level |
| `RATE_LIMIT` | `1000/minute` | SlowAPI rate limit (placeholder — monitored and tuned) |

### Adaptive Batching Config

| Field | Default | Description |
|---|---|---|
| `max_context_window` | 128000 | Sarvam model context window |
| `avg_tokens_per_ticket` | 2000 | Estimated tokens per ticket |
| `max_batch_size` | 50 | Hard cap on tickets per batch |

---

## Usage

```python
from engine.orchestrator import TicketPipeline

pipeline = TicketPipeline(sarvam_api_key="your-api-key")
await pipeline.initialize()

response = await pipeline.process_tickets(tickets)
print(response.success_count, response.failure_count)

await pipeline.cleanup()
```

---

## What's In Scope

- Adaptive batching by context window and token usage
- Retry with exponential backoff + jitter for rate limits and transient errors
- Partial failure handling — individual ticket failures do not crash the batch
- Immediate processing estimate before async work begins
- MySQL for persistence readiness (PostgreSQL planned for production)

## What's Not In Scope

- **Event Bus** — no internal pub/sub; can be added via `BaseEventBus`
- **Control Loop** — no APScheduler; single request cycle only
- **StateStore persistence** — stateless request-response
- **Worker loops** — synchronous processing within each request
- **Multi-model support** — Sarvam LLM API only

---

## Future Improvements

- **PostgreSQL** — MySQL is used for initial development. PostgreSQL is planned for production for better scalability
- **StateStore persistence** — wire `StateStoreAgent` into Reducers for state survival across restarts
- **Event Bus** — add `BaseEventBus` for decoupled pub/sub between components
- **Control Loop** — add APScheduler-based reconciliation for background monitoring

## Tradeoffs

- **Modular but complex** — The layered structure adds indirection that pays off when the service grows. For a simple one-off script, it would be overkill.
- **Boilerplate-heavy** — Each layer has its own file, lifecycle, and import path. This is intentional — it makes each piece independently testable.
- **Pydantic-first** — All data flows through validated Pydantic models. This adds upfront setup but catches errors early and provides self-documenting APIs.