# Ticket Classification Pipeline

A stateless request-response pipeline that classifies enterprise support tickets using the Sarvam LLM API. Handles batches of up to 500 tickets with adaptive batching, retry with exponential backoff, and partial failure handling.

## Architecture

The pipeline follows a layered architecture pattern:

```
engine/
  orchestrator.py         # TicketPipeline — wires all layers
  reducers.py             # TicketPipelineReducers — state mutations
  application.py          # TicketPipelineApplication — business logic
  models/
    models.py            # DomainState, TicketModel, ClassificationResult,
                         # Sarvam API models
  operators/
    operators.py         # TicketPipelineOperators — runtime state, owns HTTPAPIClient
    http_client.py        # HTTPAPIClient — Sarvam API calls with retry + backoff
```

### Layers

**Models** (`models/models.py`) — Pydantic data models only. No logic, no runtime objects. All state lives in `DomainState`:
- `TicketModel` — incoming support ticket
- `ClassificationResult` — per-ticket classification output
- `DomainState` — single source of truth for config, stats, pending tickets, results
- `SarvamClassificationRequest/Response` — typed API payloads

**Reducers** (`reducers.py`) — All state mutations go through `TicketPipelineReducers`, which provides `_pre_hook` validation and `_post_hook` DB sync via `BaseReducers`. Call-depth protection prevents invalid mutation sequences. Mutators include `add_tickets`, `add_result`, `add_results`, `increment_batches_processed`, and config updates.

**Operators** (`operators/`) — Runtime state and infrastructure. Owns the `HTTPAPIClient` instance. Manages asyncio tasks and queues when async processing is added. Application Layer accesses HTTP calls only through `self.operators.http_api_client`.

**Application** (`application.py`) — Business logic layer. Defines the public API contract and orchestrates reducers and operators. Handles adaptive batching logic, partial failure handling, and immediate estimate computation.

**Orchestrator** (`orchestrator.py`) — Constructs all layers in dependency order (Logger -> Reducers -> Operators -> Application) and exposes thin pass-through invokables that delegate to Application Layer. No business logic.

### HTTPAPIClient

Centralized in `operators/http_client.py`. This is the **only** place in the codebase where httpx is used. All external HTTP calls go through here.

Retry behavior:
- **Rate limits (429)** — respects `Retry-After` header, otherwise waits 1 second
- **Server errors (500, 502, 503, 504)** — exponential backoff with jitter (1s base, 60s max, 0.1 jitter factor)
- **Timeouts** — exponential backoff, same as server errors
- **Non-retryable errors (4xx other than 429)** — raises immediately
- Max 5 attempts before failing

## Features

**Adaptive batching** — Splits tickets into batches by token budget. Uses ~80% of the context window per batch to stay within limits. Hard cap of 50 tickets per batch.

**Partial failure handling** — Individual ticket failures are captured in `ClassificationResult` with an error field. A failed ticket does not crash the batch. The response includes both `success_count` and `failure_count`.

**Immediate processing estimate** — Before any async work begins, the pipeline returns `estimated_batches`, `estimated_tokens`, and `estimated_time_seconds`. This lets callers display progress before processing completes.

## API

### POST /processTickets

**Request:**
```json
{
  "tickets": [
    {
      "ticket_id": "TICKET-001",
      "subject": "Cannot access dashboard",
      "description": "Getting 403 error when logging in",
      "priority": "high"
    }
  ]
}
```

**Response:**
```json
{
  "success_count": 1,
  "failure_count": 0,
  "results": [
    {
      "ticket_id": "TICKET-001",
      "category": "software_issue",
      "summary": "User unable to access dashboard due to 403 permission error",
      "success": true,
      "error": null
    }
  ],
  "estimate": {
    "estimated_batches": 1,
    "estimated_tokens": 2000,
    "estimated_time_seconds": 2.0,
    "max_batch_size": 50
  }
}
```

## In Scope

- Adaptive batching by context window and token usage
- Retry with exponential backoff + jitter for rate limits (429) and transient errors (5xx, timeouts)
- Partial failure handling — individual ticket failures do not crash the batch
- Immediate processing estimate returned before async work begins
- MySQL for future scalability (PostgreSQL planned for production)

## Not In Scope

- **No Event Bus** — can be added later via `BaseEventBus`
- **No Control Loop** — no APScheduler; single request cycle only
- **No StateStore persistence** — stateless request-response, all state per-request
- **No worker loops** — synchronous processing within each request
- **No multi-model support** — Sarvam LLM API only

## Usage

```python
from engine.orchestrator import TicketPipeline

pipeline = TicketPipeline(sarvam_api_key="your-api-key")
await pipeline.initialize()

response = await pipeline.process_tickets(tickets)
print(response.success_count, response.failure_count)

await pipeline.cleanup()
```

## Configuration

Adaptive batching behavior is controlled via `BatchConfigModel`:

| Field | Default | Description |
|---|---|---|
| `max_context_window` | 128000 | Sarvam model context window |
| `avg_tokens_per_ticket` | 2000 | Estimated tokens per ticket |
| `max_batch_size` | 50 | Hard cap on tickets per batch |