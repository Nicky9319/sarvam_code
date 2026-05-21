# Performance Benchmarking

This document describes two benchmark tiers for the Ticket Pipeline.

---

## Baseline throughput constant

**`11 tickets/second`** is used for processing estimates and integration-test latency models.

| Source | Value |
|--------|------:|
| Tier 1 peak (500 tickets, 20 class / 10 sum workers) | **12.76 tickets/s** |
| Planning baseline (conservative) | **11 tickets/s** |

Tier 1 numbers are **actual measured timings** from live `POST /api/v1/tickets/parse` against **real Sarvam** (`api.sarvam.ai`). `duration_seconds` includes Sarvam network + inference latency, worker queueing, MongoDB, and summarization — not synthetic estimates.

Slowness on tiny loads (e.g. 1 ticket ≈ 4s) reflects **fixed API round-trip cost**, not server incapacity.

---

## Tier 1 — API-speed benchmarks (single request)

**Purpose:** Rough end-to-end speed when **one client** sends **one** payload. Dominated by **external API delays** and batch count (historically fixed-size batching; now **adaptive ≤1000 estimated input tokens per batch**).

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

> **Note:** Batch counts above used the earlier fixed batch size (~25 tickets/batch). With **adaptive 1000-token batching**, batch counts will differ for the same payloads; re-run Tier 1 to refresh batch columns using `processing_estimate.estimated_batch_count` and Mongo `batches.ticket_count` / `estimated_token_count`.

### Tier 1 methodology

```bash
curl -X POST http://localhost:8000/api/v1/tickets/parse \
  -H "Content-Type: application/json" \
  -d @tests/payloads/<payload_file>.json
```

Payload files:

- 1 ticket: `tests/payloads/single_ticket_hardware_battery_drain.json`
- 25 tickets: `tests/payloads/twenty_five_tickets_mixed.json`
- 50 tickets: `tests/payloads/fifty_tickets_mixed.json`
- 200 tickets: `tests/payloads/two_hundred_tickets_mixed.json`
- 500 tickets: `tests/payloads/five_hundred_tickets_mixed.json`

---

## Tier 2 — Server load benchmarks (concurrent requests)

**Purpose:** Measure how the **whole server** behaves when **multiple parallel clients** submit parse requests at different loads. Reflects contention: worker pools, rate limiter (`5/minute` on parse per client IP), MongoDB, and shared Sarvam quota. Per-request throughput is typically **lower than Tier 1** isolated runs.

| Tier | Question | Concurrency | Typical throughput |
|------|----------|-------------|-------------------|
| 1 | How fast is one real-API request? | 1 client, 1 request | Up to ~12.76 t/s |
| 2 | How does the server handle parallel load? | N simultaneous requests | Lower; documents degradation |

### Run Tier 2

```bash
# Server running on :8000
uv run python tests/benchmarks/run_load_benchmark.py --concurrency 5 --payload fifty --json-out benchmark_results/tier2_fifty_c5.json
```

Parameters:

| Flag | Example | Meaning |
|------|---------|---------|
| `--concurrency` | 3, 5, 10 | Parallel POST requests |
| `--payload` | single, twenty_five, fifty | Ticket load per request |
| `--json-out` | path | Save machine-readable results |

Record in results: `total_wall_seconds`, `aggregate_throughput_tickets_per_sec`, per-request `duration_seconds`, `success_count`, `failure_count`, `estimated_batch_count`.

### Tier 2 results

All runs: `localhost:8000`, adaptive batching (≤1000 est. tokens/batch), real Sarvam API, same client IP (rate limit `5/minute` on parse applies).

```bash
uv run python tests/benchmarks/run_load_benchmark.py --concurrency <N> --payload <single|twenty_five|fifty>
```

#### Summary table

| Concurrency | Payload | Requests | HTTP 200 | HTTP 429 | Total tickets | Wall (s) | Aggregate t/s | Tickets succeeded | Tickets failed |
|------------:|---------|--------:|---------:|---------:|--------------:|---------:|----------------:|------------------:|---------------:|
| 3 | twenty_five | 3 | 3 | 0 | 75 | 16.28 | 4.61 | 50 | 25 |
| 5 | twenty_five | 5 | 5 | 0 | 125 | 12.83 | 9.74 | **125** | **0** |
| 5 | fifty | 5 | 5 | 0 | 250 | 19.67 | 12.71 | 100 | 150 |
| 10 | fifty | 10 | 5 | **5** | 500 | 18.97 | 26.35* | **0** | 250 |

\* **Aggregate t/s at c=10 is misleading:** five requests returned **429** in ~0.4s (not processed); throughput counts all 500 ticket slots in the wall-clock window. **Effective** completed work: 5 requests × 50 failed tickets only.

#### Run: concurrency 3, payload twenty_five (25 tickets × 3)

| Req | Status | Duration (s) | Success | Failure | Batches |
|----:|-------|-------------:|--------:|--------:|--------:|
| 1 | 200 | 16.21 | 0 | 25 | 1 |
| 2 | 200 | 13.14 | 25 | 0 | 1 |
| 3 | 200 | 14.77 | 25 | 0 | 1 |

**Outcome:** 2/3 requests full success; 1/3 all failed.

#### Run: concurrency 5, payload twenty_five (25 tickets × 5)

| Req | Status | Duration (s) | Success | Failure | Batches |
|----:|-------|-------------:|--------:|--------:|--------:|
| 1 | 200 | 12.80 | 25 | 0 | 1 |
| 2 | 200 | 10.46 | 25 | 0 | 1 |
| 3 | 200 | 10.41 | 25 | 0 | 1 |
| 4 | 200 | 10.44 | 25 | 0 | 1 |
| 5 | 200 | 10.35 | 25 | 0 | 1 |

**Outcome:** **5/5 requests full success** — best reliability in Tier 2; durations ~10–13s (compare Tier 1 single 25-ticket ~8–11s).

#### Run: concurrency 5, payload fifty (50 tickets × 5)

| Req | Status | Duration (s) | Success | Failure | Batches |
|----:|-------|-------------:|--------:|--------:|--------:|
| 1 | 200 | 19.10 | 50 | 0 | 1 |
| 2 | 200 | 17.74 | 0 | 50 | 1 |
| 3 | 200 | 17.64 | 0 | 50 | 1 |
| 4 | 200 | 19.58 | 50 | 0 | 1 |
| 5 | 200 | 17.76 | 0 | 50 | 1 |

**Outcome:** 2/5 requests full success; 3/5 all failed (HTTP 200 with total classification failure).

#### Run: concurrency 10, payload fifty (50 tickets × 10)

| Req | Status | Duration (s) | Success | Failure | Batches |
|----:|-------|-------------:|--------:|--------:|--------:|
| 1 | **429** | 0.40 | 0 | 0 | — |
| 2 | **429** | 0.39 | 0 | 0 | — |
| 3 | 200 | 18.35 | 0 | 50 | 1 |
| 4 | 200 | 18.73 | 0 | 50 | 1 |
| 5 | **429** | 0.39 | 0 | 0 | — |
| 6 | 200 | 18.64 | 0 | 50 | 1 |
| 7 | **429** | 0.39 | 0 | 0 | — |
| 8 | **429** | 0.39 | 0 | 0 | — |
| 9 | 200 | 18.47 | 0 | 50 | 1 |
| 10 | 200 | 18.26 | 0 | 50 | 1 |

**Outcome:** **5/10 rate-limited (429)**; **5/10 processed but 0 successes** (250 tickets failed classification). No request completed successfully.

### Tier 2 observations

| Finding | Detail |
|---------|--------|
| **Best parallel config** | **c=5, twenty_five** — 100% request success, ~9.74 aggregate t/s |
| **Fifty-ticket contention** | Higher failure rate at c=5 (60% of requests all-fail) vs twenty_five at c=5 (0% request failure) |
| **Rate limit ceiling** | At **c=10** from one IP, half of requests get **429** (`5/minute` parse limit); burst of 10 simultaneous POSTs exceeds quota |
| **Aggregate vs effective t/s** | Parallel wall time lowers aggregate t/s denominator; c=10 headline **26.35 t/s** overstates success — use per-request success/fail counts |
| **Adaptive batching** | All completed fifty- and twenty_five-ticket runs used **1 batch** per request (`estimated_batch_count: 1`) under 1000-token cap |
| **Tier 1 vs Tier 2** | Tier 1 = single-client API speed (includes Sarvam latency). Tier 2 = multi-request load (rate limits, worker contention, batch-level failures) |

---

## Comparative analysis (Tier 1 worker tuning)

| Classification Workers | Summarization Workers | 1 Ticket | 25 Tickets | 50 Tickets | 200 Tickets | 500 Tickets |
|------------------------|----------------------:|--------:|--------:|--------:|--------:|--------:|
| 10 | 5 | 4.40s | 10.58s | 13.33s | 24.24s | 49.50s |
| 10 | 10 | 4.12s | 8.40s | 12.06s | 21.04s | 46.47s |
| 20 | 10 | 4.30s | 11.11s | 10.13s | 20.24s | 39.20s |

**Observations:**

- Increasing summarization workers from 5 to 10 improves throughput across payload sizes.
- Increasing classification workers from 10 to 20 helps large payloads (500 tickets → **12.76 t/s** peak).
- **11 t/s** baseline is conservative vs peak for estimates and tests.

---

## Related documentation

- [architecture.md](architecture.md) — Adaptive batching, timeouts, tunables
- [experiment.md](experiment.md) — Worker configuration experiments
- [tests/README.md](tests/README.md) — Unit/integration/load test commands
