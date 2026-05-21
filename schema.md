# MongoDB Schema

This document describes the MongoDB schema for the Ticket Pipeline system.

---

## Overview

The database (`ticket_pipeline`) contains 4 collections:
- `requests` — Tracks incoming parse requests
- `batches` — Groups of tickets processed together
- `tickets` — Individual ticket records
- `metrics` — Performance metrics for completed requests

---

## Collections

### requests

Stores incoming ticket parse requests.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | string (UUID4) | Yes | Unique request identifier, auto-generated |
| `state` | string (enum) | Yes | Request state: `classification`, `summarization`, `completed` |
| `response_summary` | string or null | No | Consolidated summary from summarization |
| `createdAt` | date | Yes | Timestamp when request was created |
| `updatedAt` | date | Yes | Timestamp when request was last updated |

### batches

Groups of tickets (max 25 per batch) processed together.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `batch_id` | string (UUID4) | Yes | Unique batch identifier, auto-generated |
| `batch_number` | int | Yes | Auto-incremented batch number per request |
| `request_id` | string (UUID4) | Yes | Reference to parent request |
| `batch_state` | string (enum) | Yes | Batch state: `queued`, `processing`, `processed` |
| `batch_summary` | string or null | No | Summary from classification for this batch |
| `createdAt` | date | Yes | Timestamp when batch was created |
| `updatedAt` | date | Yes | Timestamp when batch was last updated |

### tickets

Individual ticket records within a batch.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ticket_id` | string | Yes | Unique ticket identifier (sequential: 1..N per request) |
| `request_id` | string (UUID4) | Yes | Reference to parent request |
| `batch_id` | string (UUID4) | Yes | Reference to parent batch |
| `batch_number` | int | Yes | Batch number this ticket belongs to |
| `content` | string | Yes | Original ticket text |
| `state` | string (enum) | Yes | Ticket state: `completed`, `queued`, `failed` |
| `response` | string or null | No | Classification result from LLM |
| `createdAt` | date | Yes | Timestamp when ticket was created |
| `updatedAt` | date | Yes | Timestamp when ticket was last updated |

### metrics

Performance metrics recorded after each request completes.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | string (UUID4) | Yes | Reference to parent request |
| `duration_seconds` | number | Yes | Time in seconds taken to process the request |
| `classification_worker_count` | int | Yes | Number of classification workers used |
| `summarization_worker_count` | int | Yes | Number of summarization workers used |
| `batch_count` | int | Yes | Number of batches formed for this request |
| `ticket_count` | int | Yes | Number of tickets in the request |
| `success_count` | int | Yes | Number of successfully classified tickets |
| `failure_count` | int | Yes | Number of failed tickets |
| `createdAt` | date | Yes | Timestamp when metrics were recorded |

---

## State Transitions

### Request State Machine

```
classification → summarization → completed
```

### Batch State Machine

```
queued → processing → processed
```

### Ticket State Machine

```
queued → completed (on successful classification)
queued → failed (on failed classification or no match)
```

---

## Relationships

```
requests (1) ──── (N) batches
batches (1) ──── (N) tickets
requests (1) ──── (1) metrics
```

- One `request` can have multiple `batches`
- One `batch` can have multiple `tickets`
- One `request` has one `metrics` record upon completion

---

## Schema Definition

The schema is defined in `engine/operators/db/schema.json` with JSON schema validation at the collection level.

See [schema.json](engine/operators/db/schema.json) for the full JSON schema definition.