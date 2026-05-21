# Performance Benchmarking

This document contains performance benchmark results for the Ticket Pipeline system.

**Note:** Benchmark results depend on the worker configuration. See [.env](../.env) for current settings and [experiment.md](experiment.md) for the experiment guide.

---

## Configuration

Before running benchmarks, set worker counts in `.env`:

```bash
CLASSIFICATION_WORKER_COUNT=10
SUMMARIZATION_WORKER_COUNT=5
```

---

## Benchmark Results

*To be populated with benchmark data.*

### Default Configuration (10 / 5)

| Tickets | Batches | Duration (s) | Throughput (tickets/s) |
|--------:|--------:|-------------:|----------------------:|
| - | - | - | - |

---

## Benchmark Methodology

Run benchmarks using:

```bash
curl -X POST http://localhost:8000/api/v1/tickets/parse \
  -H "Content-Type: application/json" \
  -d @tests/payloads/<payload_file>.json
```

The `duration_seconds` field in the response indicates total processing time.

Payload files:
- 1 ticket: `tests/payloads/single_ticket_hardware_battery_drain.json`
- 25 tickets: `tests/payloads/twenty_five_tickets_mixed.json`
- 50 tickets: `tests/payloads/fifty_tickets_mixed.json`
- 200 tickets: `tests/payloads/two_hundred_tickets_mixed.json`
- 500 tickets: `tests/payloads/five_hundred_tickets_mixed.json`

---

## Comparative Analysis

*To be populated with benchmark comparisons across different worker configurations.*

---

## Related Documentation

- [architecture.md](architecture.md) — System architecture and tunable parameters
- [experiment.md](experiment.md) — Guide to benchmarking different worker configurations