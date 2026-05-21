# Ticket Pipeline

Classifies support tickets with the Sarvam API using **adaptive batching**, and returns per-ticket categories plus a consolidated summary.

---

## Adaptive batching and token assumption

Tickets are grouped into batches so the **sum of estimated input tokens per batch** does not exceed `MAX_BATCH_TOKENS` (default **1000**, env-configurable).

**Token estimate assumption (documented for this project):**

> **1 token = 1 English character** in the ticket text (`len(ticket_string)`).

This is a deliberate simplification (not a Sarvam/OpenAI tokenizer). It makes batch limits easy to reason about and tends to form **smaller batches** than `chars ÷ 4` heuristics. System prompts and JSON wrapping in the API request are **not** included in this count—only each ticket’s raw string.

Example: fifty short tickets (~80 characters each) ≈ **4000 estimated tokens** → about **four batches** at `MAX_BATCH_TOKENS=1000`, not one batch.

---

## Retries and parse failures

| Stage | Retried? | Details |
|-------|----------|---------|
| **Sarvam HTTP call** (classification / summarization) | **Yes** | Up to **3 attempts** with exponential backoff + jitter (`tenacity` on `invoke_sarvam_*`). Includes network errors and HTTP timeouts (`SARVAM_HTTP_TIMEOUT`, default 120s). |
| **JSON parse** of classification response | **No** | If the API returns but the body is not valid JSON (e.g. `JSONDecodeError`), the **entire batch** is marked failed once—no re-call to Sarvam for that batch. |
| **Per-ticket mapping** (wrong/missing `ticket_id` from model) | **No** | Unmatched tickets are marked `failed`; matched ones succeed (partial success within a batch). |

So a failure like `Expecting value: line 1 column 1 (char 0)` means Sarvam likely returned successfully (retries already exhausted on transport), but **parsing** failed—typically empty/non-JSON output or output truncated by `max_tokens=2000` on classification.

---

## Setup (Docker Compose)

Clone the repo, configure environment variables, build images, and start all services:

```bash
git clone https://github.com/Nicky9319/sarvam_code.git
cd main   # repo root
cp .env.local .env
# Edit .env and set SARVAM_API_KEY

docker compose build
docker compose up -d
```

Check the API is up:

```bash
curl http://localhost:8000/api/v1/tickets/health
```

View app logs:

```bash
docker compose logs -f ticket-pipeline
```

Stop services:

```bash
docker compose down
```

Run curl commands from the **repo root** on your host (port `8000` is published to `localhost`). Payload files are under `tests/payloads/`.

`MONGODB_HOST=mongodb` is set for the app container in `docker-compose.yml`.

---

## Parse API — curl by load level

Use `-d @<file.json>` to send the body from a payload file (recommended — no quoting issues).

| Tickets | Payload file | Notes |
|--------:|--------------|-------|
| 1 | `tests/payloads/single_ticket_hardware_battery_drain.json` | Batch count depends on adaptive token packing |
| 25 | `tests/payloads/twenty_five_tickets_mixed.json` | See `processing_estimate.estimated_batch_count` in response |
| 50 | `tests/payloads/fifty_tickets_mixed.json` | |
| 200 | `tests/payloads/two_hundred_tickets_mixed.json` | |
| 500 | `tests/payloads/five_hundred_tickets_mixed.json` | |

API maximum is **500 tickets** per request.

### 1 ticket

```bash
curl -X POST http://localhost:8000/api/v1/tickets/parse \
  -H "Content-Type: application/json" \
  -d @tests/payloads/single_ticket_hardware_battery_drain.json
```

### 25 tickets

```bash
curl -X POST http://localhost:8000/api/v1/tickets/parse \
  -H "Content-Type: application/json" \
  -d @tests/payloads/twenty_five_tickets_mixed.json
```

### 50 tickets

```bash
curl -X POST http://localhost:8000/api/v1/tickets/parse \
  -H "Content-Type: application/json" \
  -d @tests/payloads/fifty_tickets_mixed.json
```

### 200 tickets

```bash
curl -X POST http://localhost:8000/api/v1/tickets/parse \
  -H "Content-Type: application/json" \
  -d @tests/payloads/two_hundred_tickets_mixed.json
```

### 500 tickets (max)

```bash
curl -X POST http://localhost:8000/api/v1/tickets/parse \
  -H "Content-Type: application/json" \
  -d @tests/payloads/five_hundred_tickets_mixed.json
```

### Inline JSON (no file — single line only)

```bash
curl -X POST http://localhost:8000/api/v1/tickets/parse -H "Content-Type: application/json" -d '{"tickets":["Cannot login to my account, it keeps saying wrong password","Server is down at our office"]}'
```

For larger payloads, use `-d @tests/payloads/<file>.json` instead of inline JSON.

> **Avoid:** `parse \ -H` (space after `\`) or splitting `Content-Type:` across lines — the body will not be sent.

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/tickets/health` | Health check |
| `POST` | `/api/v1/tickets/parse` | Classify tickets and return summary |

**Request body:**

```json
{
  "tickets": ["ticket text 1", "ticket text 2"]
}
```

**Response:** `success`, `failures`, `summary`.

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `SARVAM_API_KEY` | Sarvam API key (required) |
| `SARVAM_BASE_URL` | Default `https://api.sarvam.ai/v1` |
| `MONGODB_HOST` | Set to `mongodb` via `docker-compose.yml` |
| `MONGODB_PORT` | Default `27017` |
| `LOG_LEVEL` | Default `INFO` |
| `MAX_BATCH_TOKENS` | Max estimated **input** tokens per batch (1 token = 1 char); default `1000` |
| `SARVAM_HTTP_TIMEOUT` | HTTP timeout for Sarvam client (seconds); default `120` |
| `CLASSIFICATION_WORKER_COUNT` | Parallel classification workers; default `10` |
| `SUMMARIZATION_WORKER_COUNT` | Parallel summarization workers; default `5` |

---

## Docs

- [Architecture](architecture.md) - System architecture, pipeline diagrams, and tunable parameters
- [Benchmark](benchmark.md) - Performance benchmarks and tuning results
- [Future Improvements](future_improvements.md) - Planned enhancements and features
- [Parse request flow](docs/PARSE_REQUEST_FLOW.md)
