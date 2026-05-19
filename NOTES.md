# Notes — Ticket Classification Pipeline

## Architecture Tradeoffs

This pipeline uses a modular layered architecture (class-generator pattern):
- **Pros**: Modular, testable, room to add more components (event bus, control loop, worker loops)
- **Cons**: Over-engineered for a stateless request-response service; adds indirection that a simpler FastAPI endpoint wouldn't need

The class-generator pattern is designed for long-running stateful services with restart recovery. A ticket classification pipeline is stateless — each request is independent. Some layers (StateStore, Control Loop, Event Bus) were excluded as a result.

## Assumptions

- Sarvam LLM API is available and credentials are provided via environment/config
- Tickets are pre-validated before arriving at the pipeline (no input sanitization in pipeline)
- No multi-tenancy — all tickets in a batch belong to the same context
- Context window of 128k tokens, using ~80% (102k) as safe batch budget
- Average 2000 tokens per ticket estimate (subject + description)
- Batch processing is synchronous within a single request (no background workers)

## Future Improvements

### PostgreSQL Migration
Currently the engine uses a minimal StateStore stub. For production scalability, migrate to PostgreSQL:
- Replace aiosqlite-based StateStore with asyncpg (async PostgreSQL driver)
- Add connection pooling via asyncpg pool
- Benefits: better concurrency, ACID compliance, production-grade reliability
- StateStore sidecar interface stays the same — only the engine implementation changes

### Other Future Improvements
- **Event Bus**: Add BaseEventBus for internal pub/sub (batch_started, retry_exhausted, etc.)
- **Control Loop**: APScheduler-based loop for background reconciliation
- **Worker Loops**: Background asyncio workers for large batch processing
- **Caching**: Redis cache for repeated ticket patterns
- **Circuit Breaker**: Per-batch failure circuit breaker to avoid hammering failing API
- **Batch Parallelization**: Process multiple batches concurrently (limited by API rate limits)

## Configuration

The following values are currently hardcoded and will be moved to environment variables in a future iteration:
- **Sarvam API key** (`sarvam_api_key`) — used for LLM API authentication
- **Sarvam base URL** (`sarvam_base_url`) — API endpoint, defaults to `https://api.sarvam.ai`
- **MySQL connection** — host, port, user, password, database — passed at initialization
- **Batch config** — `max_context_window`, `avg_tokens_per_ticket`, `max_batch_size` — defined in `BatchConfigModel` with defaults

Planned approach: use a `.env` file + `pydantic-settings` or similar for runtime config injection.

## Rate Limiting

Currently using SlowAPI with an initial limit of **1000 req/min** (keyed by client IP). This is a placeholder value — to be monitored and optimized based on actual traffic patterns in production.

## API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/v1/tickets/health` | GET | Health check |
| `/api/v1/tickets/processTickets` | POST | Classify tickets (placeholder) |