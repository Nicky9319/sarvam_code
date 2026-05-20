# Setup & Running Instructions

## 1. Configure Environment Variables

Before running anything, copy and edit the `.env` file:

```bash
cp .env.example .env  # if .env.example exists
# OR manually edit .env and set your values
```

**Critical** — set your Sarvam API key:
```
SARVAM_API_KEY=your-actual-key-here
```

> ⚠️ **Important**: If `SARVAM_API_KEY` is not set or is a placeholder, the server will return arbitrary/incorrect responses from the LLM. Always use a valid key.

## 2. Build & Start Services

```bash
docker compose build
docker compose up -d
```

## 3. Verify Services Are Running

```bash
docker compose ps
```

You should see `ticket-pipeline` and `mongodb` both running.

## 4. Test the API

**Health check:**
```bash
curl http://localhost:8000/api/v1/tickets/health
```

**Parse endpoint (supports up to 500 tickets in a single call):**
```bash
curl -X POST http://localhost:8000/api/v1/tickets/parse \
  -H "Content-Type: application/json" \
  -d '{"tickets": ["Cannot login to my account, it keeps saying wrong password", "Server is down at our office"]}'
```

## 5. View Logs

```bash
docker compose logs -f ticket-pipeline
```

## 6. Stop Everything

```bash
docker compose down
```

## 7. Persist Data

MongoDB data is stored in a Docker volume (`mongodb_data`) and survives restarts. Your `.env` file is gitignored — keep it safe to preserve your secrets across fresh clones.