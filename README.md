# Ticket Pipeline

Classifies support tickets with the Sarvam API, batches them (25 per batch), and returns per-ticket categories plus a consolidated summary.

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

| Tickets | Batches | Payload file |
|--------:|--------:|--------------|
| 1 | 1 | `tests/payloads/single_ticket_hardware_battery_drain.json` |
| 25 | 1 | `tests/payloads/twenty_five_tickets_mixed.json` |
| 50 | 2 | `tests/payloads/fifty_tickets_mixed.json` |
| 200 | 8 | `tests/payloads/two_hundred_tickets_mixed.json` |
| 500 | 20 | `tests/payloads/five_hundred_tickets_mixed.json` |

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

---

## Docs

- [Architecture](architecture.md) - System architecture, pipeline diagrams, and tunable parameters
- [Benchmark](benchmark.md) - Performance benchmarks and tuning results
- [Parse request flow](docs/PARSE_REQUEST_FLOW.md)
