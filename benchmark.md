# Performance Benchmarking

This document contains performance benchmark results for the Ticket Pipeline system.

---

## Benchmark Results

### Configuration: 10 Classification Workers / 5 Summarization Workers

| Tickets | Batches | Duration (s) | Throughput (tickets/s) |
|--------:|--------:|-------------:|----------------------:|
| 1 | 1 | 4.40 | 0.23 |
| 25 | 1 | 10.58 | 2.36 |
| 50 | 2 | 13.33 | 3.75 |
| 200 | 8 | 24.24 | 8.25 |
| 500 | 20 | 49.50 | 10.10 |

### Configuration: 10 Classification Workers / 10 Summarization Workers

| Tickets | Batches | Duration (s) | Throughput (tickets/s) |
|--------:|--------:|-------------:|----------------------:|
| 1 | 1 | 4.12 | 0.24 |
| 25 | 1 | 8.40 | 2.98 |
| 50 | 2 | 12.06 | 4.15 |
| 200 | 8 | 21.04 | 9.51 |
| 500 | 20 | 46.47 | 10.76 |

### Configuration: 20 Classification Workers / 10 Summarization Workers

| Tickets | Batches | Duration (s) | Throughput (tickets/s) |
|--------:|--------:|-------------:|----------------------:|
| 1 | 1 | 4.30 | 0.23 |
| 25 | 1 | 11.11 | 2.25 |
| 50 | 2 | 10.13 | 4.94 |
| 200 | 8 | 20.24 | 9.88 |
| 500 | 20 | 39.20 | 12.76 |

---

## Comparative Analysis

| Classification Workers | Summarization Workers | 1 Ticket | 25 Tickets | 50 Tickets | 200 Tickets | 500 Tickets |
|------------------------|----------------------:|--------:|--------:|--------:|--------:|--------:|
| 10 | 5 | 4.40s | 10.58s | 13.33s | 24.24s | 49.50s |
| 10 | 10 | 4.12s | 8.40s | 12.06s | 21.04s | 46.47s |
| 20 | 10 | 4.30s | 11.11s | 10.13s | 20.24s | 39.20s |

**Key Observations:**
- Increasing summarization workers from 5 to 10 improves throughput across all payload sizes
- Increasing classification workers from 10 to 20 significantly improves performance for larger payloads (500 tickets)
- 20/10 configuration achieves the best throughput for 500 tickets (12.76 tickets/s)

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

## Related Documentation

- [architecture.md](architecture.md) — System architecture and tunable parameters
- [experiment.md](experiment.md) — Guide to benchmarking different worker configurations