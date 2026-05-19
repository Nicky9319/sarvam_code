# Ticket Classification Pipeline — Engine

Production-grade pipeline for classifying enterprise support tickets using Sarvam's LLM API.

## Architecture

Built on the class-generator layered pattern. Layers (bottom-up):

```
Models          → DomainState + Pydantic request/response models
Reducers        → BaseReducers subclass, all state mutations
Application     → Business logic (adaptive batching, partial failures)
Operators       → HTTPAPIClient (Sarvam API), runtime state
Orchestrator    → Wires all layers, public API
```

**Key design decisions:**
- **Stateless**: request-response only, no StateStore persistence needed
- **No Event Bus** (for now): internal events can be added later via BaseEventBus
- **No Control Loop**: no APScheduler — single request cycle only
- **No worker loops**: all processing is synchronous within a single request

## Features

| Feature | Implementation |
|---------|----------------|
| Adaptive batching | `_create_adaptive_batches()` — splits by token budget |
| Retry + backoff | `HTTPAPIClient` — exponential backoff + jitter |
| Partial failure | `ProcessTicketsResponse` — `success_count` + `failure_count` |
| Immediate estimate | `process_tickets(estimate_only=True)` — before async work |

## File Structure

```
engine/
├── __init__.py                  # Public exports
├── orchestrator.py               # TicketPipeline orchestrator
├── reducers.py                   # TicketPipelineReducers (BaseReducers)
├── application.py               # TicketPipelineApplication (business logic)
├── models/
│   ├── __init__.py
│   └── models.py                # DomainState + request/response models
└── operators/
    ├── __init__.py
    ├── operators.py             # TicketPipelineOperators (runtime state)
    └── http_client.py          # HTTPAPIClient (Sarvam API, retry/backoff)
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

- **Event Bus** — no internal pub/sub events yet
- **Control Loop** — no APScheduler (no continuous reconciliation)
- **StateStore persistence** — all state is per-request only
- **Worker loops** — no background asyncio tasks