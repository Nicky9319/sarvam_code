# Performance Experiments

This document guides you through benchmarking different worker configurations for the Ticket Pipeline.

---

## Overview

The pipeline's throughput is governed by two key parallelization parameters:

- **`CLASSIFICATION_WORKER_COUNT`** — Number of parallel workers for ticket classification
- **`SUMMARIZATION_WORKER_COUNT`** — Number of parallel workers for summary generation

Both are configurable via environment variables in `.env` or `.env.local`.

---

## Quick Experiment

### Step 1: Set Worker Counts

Edit `.env.local`:

```bash
CLASSIFICATION_WORKER_COUNT=10
SUMMARIZATION_WORKER_COUNT=5
```

### Step 2: Run Benchmark

```bash
curl -X POST http://localhost:8000/api/v1/tickets/parse \
  -H "Content-Type: application/json" \
  -d @tests/payloads/five_hundred_tickets_mixed.json
```

Note the `duration_seconds` in the response.

### Step 3: Change and Repeat

Modify the worker counts, restart the service, and re-run. Compare `duration_seconds` across configurations.

---

## Experiment Matrix

A typical experiment would vary worker counts across the following values:

| Classification Workers | Summarization Workers | Expected Behavior |
|------------------------|----------------------|-------------------|
| 1 | 1 | Baseline (slow) |
| 5 | 3 | Balanced |
| 10 | 5 | Default |
| 20 | 10 | High parallelism |
| 50 | 10 | Very high classification parallelism |

### Things to Measure

1. **`duration_seconds`** — Total end-to-end latency
2. **Classification stage time** — Time from request to classification complete
3. **Summarization stage time** — Time from classification complete to summary ready
4. **Throughput** — Tickets processed per second (`ticket_count / duration_seconds`)

---

## Interpreting Results

### Classification Bottleneck
If increasing `CLASSIFICATION_WORKER_COUNT` improves throughput but `SUMMARIZATION_WORKER_COUNT` has little effect → classification stage is the bottleneck.

### Summarization Bottleneck
If increasing `SUMMARIZATION_WORKER_COUNT` improves throughput but `CLASSIFICATION_WORKER_COUNT` has little effect → summarization stage is the bottleneck.

### Diminishing Returns
At some point, adding more workers won't help due to:
- Sarvam API rate limits
- MongoDB connection pool limits
- Network latency saturation

---

## Recording Results

Record your findings in [benchmark.md](benchmark.md):

```bash
# Example entry
## 10 Classification / 5 Summarization (Default)

| Tickets | Batches | Duration (s) | Throughput (tickets/s) |
|--------:|--------:|-------------:|----------------------:|
| 500     | 20      | 12.34        | 40.5                  |
```

---

## Related Documentation

- [architecture.md](architecture.md) — System architecture and tunable parameters
- [benchmark.md](benchmark.md) — Performance benchmark results