# Tests

## Layout

| Directory | Purpose |
|-----------|---------|
| `unit/` | Fast tests with mocked I/O |
| `integration/` | Pipeline and latency model tests |
| `benchmarks/` | Tier 2 load benchmark script (live server) |
| `payloads/` | JSON fixtures for curl and load runs |

## Commands

```bash
# Unit tests only (default CI)
uv run pytest tests/unit -q

# Integration tests (no live Sarvam)
uv run pytest tests/integration -q

# Exclude slow load benchmarks
uv run pytest tests -m "not load" -q

# Tier 2 load benchmark (server must be running)
uv run python tests/benchmarks/run_load_benchmark.py --concurrency 5 --payload fifty
```

## Latency model

Integration tests use `BASELINE_THROUGHPUT_TICKETS_PER_SEC = 11` from real Tier 1 Sarvam API benchmarks (see [benchmark.md](../benchmark.md)).
